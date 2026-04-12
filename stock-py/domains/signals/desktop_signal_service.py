from __future__ import annotations

import inspect
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from domains.signals.dedupe_policy import SignalDedupePolicy
from domains.signals.exit_level_calculator import ExitLevelCalculator
from domains.signals.repository import SignalRepository
from domains.signals.schemas import DesktopSignalRequest
from infra.events.outbox import OutboxPublisher


class DesktopSignalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SignalRepository(session)
        self.dedupe_policy = SignalDedupePolicy()
        self.outbox = OutboxPublisher(session)
        self.exit_level_calculator = ExitLevelCalculator()

    async def ingest_desktop_signal(self, request: DesktopSignalRequest) -> dict[str, Any]:
        strategy_window = self._strategy_window(request)
        market_regime = self._market_regime(request)
        analysis = dict(request.analysis)
        active_calibration_snapshot = await self.load_active_calibration_snapshot()
        self._apply_active_calibration_snapshot(analysis, active_calibration_snapshot)
        exit_levels = self.exit_level_calculator.calculate(
            signal_type=request.alert.type,
            entry_price=request.alert.price,
            market_snapshot=request.alert.model_dump(mode="python"),
            analysis=analysis,
            market_regime=market_regime,
            risk_reward_ratio=self._coerce_float(analysis.get("risk_reward_ratio")),
        )
        analysis["exit_levels"] = exit_levels
        dedupe_key = self.dedupe_policy.build_dedupe_key(
            request.alert.symbol,
            request.alert.type,
            strategy_window,
            market_regime,
        )
        duplicate = await self.repository.find_recent_duplicate(
            symbol=request.alert.symbol,
            signal_type=request.alert.type,
            dedupe_key=dedupe_key,
            cooldown_minutes=int(request.analysis.get("cooldown_minutes", 60)),
        )
        if duplicate is not None:
            duplicate_metadata = self.repository._load_metadata(duplicate)
            if self.dedupe_policy.should_suppress(
                existing_generated_at=duplicate.generated_at,
                existing_dedupe_key=duplicate_metadata.get("dedupe_key"),
                candidate_dedupe_key=dedupe_key,
            ):
                return {
                    "signal_id": duplicate.id,
                    "dedupe_key": dedupe_key,
                    "suppressed": True,
                    "queued_recipient_count": 0,
                    "status": "suppressed",
                }

        signal = await self.repository.create_signal(
            {
                "symbol": request.alert.symbol,
                "signal_type": request.alert.type,
                "status": "pending",
                "entry_price": request.alert.price,
                "stop_loss": exit_levels.get("stop_loss"),
                "take_profit_1": exit_levels.get("take_profit_1"),
                "take_profit_2": exit_levels.get("take_profit_2"),
                "take_profit_3": exit_levels.get("take_profit_3"),
                "probability": request.alert.probability or analysis.get("probability", 0),
                "confidence": request.alert.confidence or request.alert.score,
                "risk_reward_ratio": analysis.get("risk_reward_ratio"),
                "sfp_validated": bool(analysis.get("sfp_validated", False)),
                "chooch_validated": bool(analysis.get("chooch_validated", False)),
                "fvg_validated": bool(analysis.get("fvg_validated", False)),
                "validation_status": str(analysis.get("validation_status", "validated")),
                "atr_value": analysis.get("atr_value") or exit_levels.get("atr_value"),
                "atr_multiplier": analysis.get("atr_multiplier") or exit_levels.get("atr_multiplier") or 2.0,
                "reasoning": self._reasoning(request.alert.reasons),
                "analysis": analysis,
                "source": request.source,
                "emitted_at": request.emitted_at.isoformat(),
                "strategy_window": strategy_window,
                "market_regime": market_regime,
                "dedupe_key": dedupe_key,
                "generated_at": self._normalize_emitted_at(request.emitted_at),
            }
        )
        await self.route_signal(signal.id, request, dedupe_key=dedupe_key, analysis=analysis)
        return {
            "signal_id": signal.id,
            "dedupe_key": dedupe_key,
            "suppressed": False,
            "queued_recipient_count": 0,
            "status": "accepted",
        }

    async def route_signal(
        self,
        signal_id: int,
        request: DesktopSignalRequest,
        dedupe_key: str,
        recipient_ids: list[int] | None = None,
        analysis: dict[str, Any] | None = None,
    ) -> None:
        payload_analysis = analysis if isinstance(analysis, dict) else request.analysis
        payload = {
            "signal_id": str(signal_id),
            "symbol": request.alert.symbol,
            "signal_type": request.alert.type,
            "price": request.alert.price,
            "score": request.alert.score,
            "reasons": request.alert.reasons,
            "analysis": payload_analysis,
            "source": request.source,
            "user_ids": recipient_ids or [],
            "strategy_window": self._strategy_window(request),
            "market_regime": self._market_regime(request),
            "dedupe_key": dedupe_key,
        }
        await self.outbox.publish_after_commit(
            topic="signal.generated",
            key=str(signal_id),
            payload=payload,
        )
        await self.outbox.publish_after_commit(
            topic="ops.audit.logged",
            key=str(signal_id),
            payload={
                "entity": "signal",
                "entity_id": signal_id,
                "action": "desktop.ingested",
                "source": request.source,
                "symbol": request.alert.symbol,
            },
        )

    async def load_active_calibration_snapshot(self) -> dict[str, Any] | None:
        execute = getattr(self.session, "execute", None)
        if not callable(execute):
            return None

        from domains.signals.calibration_repository import SignalCalibrationSnapshotRepository

        snapshot = await SignalCalibrationSnapshotRepository(self.session).get_active_snapshot()
        if not isinstance(snapshot, dict):
            return None
        return {
            "version": snapshot.get("version"),
            "source": snapshot.get("source"),
            "effective_from": snapshot.get("effective_from") or snapshot.get("effective_at"),
            "strategy_weights": dict(snapshot.get("strategy_weights") or {}),
            "score_multipliers": dict(snapshot.get("score_multipliers") or {}),
            "atr_multipliers": dict(snapshot.get("atr_multipliers") or {}),
        }

    @staticmethod
    def _apply_active_calibration_snapshot(
        analysis: dict[str, Any],
        snapshot: dict[str, Any] | None,
    ) -> None:
        if not isinstance(snapshot, dict) or not snapshot:
            return

        if not isinstance(analysis.get("calibration_snapshot"), dict):
            analysis["calibration_snapshot"] = {
                "version": snapshot.get("version"),
                "source": snapshot.get("source"),
                "effective_from": snapshot.get("effective_from") or snapshot.get("effective_at"),
                "strategy_weights": dict(snapshot.get("strategy_weights") or {}),
                "score_multipliers": dict(snapshot.get("score_multipliers") or {}),
                "atr_multipliers": dict(snapshot.get("atr_multipliers") or {}),
            }

        version = str(snapshot.get("version") or "").strip()
        if version and not str(analysis.get("calibration_version") or "").strip():
            analysis["calibration_version"] = version

        for block_name in ("strategy_selection", "score_breakdown"):
            block = analysis.get(block_name)
            if isinstance(block, dict) and version and not str(block.get("calibration_version") or "").strip():
                block["calibration_version"] = version

    @staticmethod
    def _reasoning(reasons: list[str]) -> str | None:
        items = [reason.strip() for reason in reasons if reason.strip()]
        return "; ".join(items) if items else None

    @staticmethod
    def _strategy_window(request: DesktopSignalRequest) -> str:
        return str(
            request.analysis.get("strategy_window") or request.alert.strategy_window or "default"
        )

    @staticmethod
    def _market_regime(request: DesktopSignalRequest) -> str:
        return str(
            request.analysis.get("market_regime") or request.alert.market_regime or "unknown"
        )

    @staticmethod
    def _normalize_emitted_at(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
