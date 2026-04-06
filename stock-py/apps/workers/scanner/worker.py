from __future__ import annotations

import asyncio
import inspect
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Sequence

from domains.signals.dedupe_policy import SignalDedupePolicy
from domains.signals.live_strategy_engine import LiveStrategyEngine
from infra.observability.runtime_monitoring import run_runtime_monitored

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ScannerWorker:
    def __init__(
        self,
        *,
        poll_interval_seconds: int = 300,
        bucket_count: int = 32,
        cooldown_minutes: int = 60,
        live_strategy_engine: LiveStrategyEngine | None = None,
        market_snapshot_provider: Any | None = None,
    ) -> None:
        self.poll_interval = poll_interval_seconds
        self.bucket_count = bucket_count
        self.cooldown_minutes = cooldown_minutes
        self.live_strategy_engine = live_strategy_engine or LiveStrategyEngine()
        self.market_snapshot_provider = market_snapshot_provider
        self.dedupe_policy = SignalDedupePolicy(cooldown_minutes=cooldown_minutes)
        self._running = False

    async def run_forever(
        self,
        *,
        bucket_ids: Sequence[int] | None = None,
        initial_delay: float = 5.0,
    ) -> None:
        logger.info("Starting scanner worker")
        await asyncio.sleep(initial_delay)
        self._running = True
        while self._running:
            try:
                await self.run_once(bucket_ids=bucket_ids)
            except Exception:
                logger.exception("Scanner worker cycle failed")
            await asyncio.sleep(self.poll_interval)
        logger.info("Scanner worker stopped")

    async def run_once(self, *, bucket_ids: Sequence[int] | None = None) -> dict[str, int]:
        items = await self.list_scan_buckets()
        grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            bucket_item = self._normalize_bucket_item(item)
            grouped[bucket_item["bucket_id"]].append(bucket_item)

        selected = set(bucket_ids or grouped.keys())
        stats = {
            "buckets": 0,
            "scanned": 0,
            "emitted": 0,
            "suppressed": 0,
            "skipped": 0,
            "errors": 0,
        }
        for bucket_id in sorted(selected):
            bucket_items = grouped.get(bucket_id, [])
            if not bucket_items:
                continue
            result = await self.process_bucket(bucket_id, bucket_items)
            stats["buckets"] += 1
            stats["scanned"] += result["scanned"]
            stats["emitted"] += result["emitted"]
            stats["suppressed"] += result["suppressed"]
            stats["skipped"] += result["skipped"]
            stats["errors"] += result["errors"]
        return stats

    async def process_bucket(
        self,
        bucket_id: int,
        bucket_items: Sequence[dict[str, Any]],
    ) -> dict[str, int]:
        session = await self.open_session()
        run = None
        stats = {"scanned": 0, "emitted": 0, "suppressed": 0, "skipped": 0, "errors": 0}
        try:
            run = await self.create_run(session, bucket_id)
            for item in bucket_items:
                stats["scanned"] += 1
                try:
                    result = await self.process_symbol(
                        session,
                        run_id=self._extract_run_id(run),
                        symbol=item["symbol"],
                        priority=item.get("priority", 0),
                    )
                except Exception as exc:
                    stats["errors"] += 1
                    await self.record_decision(
                        session,
                        run_id=self._extract_run_id(run),
                        symbol=item["symbol"],
                        decision="error",
                        reason=f"{type(exc).__name__}: {exc}",
                        signal_type=None,
                        score=None,
                        suppressed=False,
                        dedupe_key=None,
                    )
                    logger.exception("Scanner worker failed processing symbol=%s", item["symbol"])
                    continue

                if result["status"] == "emitted":
                    stats["emitted"] += 1
                elif result["status"] == "suppressed":
                    stats["suppressed"] += 1
                else:
                    stats["skipped"] += 1

            await self.finish_run(
                session,
                run,
                status="completed",
                scanned_count=stats["scanned"],
                emitted_count=stats["emitted"],
                suppressed_count=stats["suppressed"],
                error_message=None,
            )
            await self.commit_session(session)
            return stats
        except Exception as exc:
            if run is not None:
                await self.finish_run(
                    session,
                    run,
                    status="failed",
                    scanned_count=stats["scanned"],
                    emitted_count=stats["emitted"],
                    suppressed_count=stats["suppressed"],
                    error_message=str(exc),
                )
                await self.commit_session(session)
            raise
        finally:
            await self.close_session(session)

    async def process_symbol(
        self,
        session: Any,
        *,
        run_id: int,
        symbol: str,
        priority: int = 0,
    ) -> dict[str, Any]:
        snapshot = await self.load_market_snapshot(symbol, session, priority=priority)
        if not snapshot:
            await self.record_decision(
                session,
                run_id=run_id,
                symbol=symbol,
                decision="skipped",
                reason="market_snapshot_unavailable",
                signal_type=None,
                score=None,
                suppressed=False,
                dedupe_key=None,
            )
            return {"status": "skipped"}

        candidate = self.live_strategy_engine.build_signal_candidate(
            symbol,
            snapshot,
            {"priority": priority},
        )
        if candidate is None:
            await self.record_decision(
                session,
                run_id=run_id,
                symbol=symbol,
                decision="skipped",
                reason="candidate_not_generated",
                signal_type=None,
                score=None,
                suppressed=False,
                dedupe_key=None,
            )
            return {"status": "skipped"}

        candidate_data = self._candidate_to_dict(candidate)
        strategy_window = str(
            candidate_data.get("strategy_window")
            or candidate_data.get("analysis", {}).get("strategy_window")
            or "default"
        )
        market_regime = str(
            candidate_data.get("market_regime")
            or candidate_data.get("analysis", {}).get("market_regime")
            or "unknown"
        )
        dedupe_key = self.dedupe_policy.build_dedupe_key(
            symbol,
            str(candidate_data["type"]),
            strategy_window,
            market_regime,
        )

        duplicate = await self.find_recent_duplicate(
            session,
            symbol=symbol,
            signal_type=str(candidate_data["type"]),
            dedupe_key=dedupe_key,
        )
        if duplicate is not None:
            await self.record_decision(
                session,
                run_id=run_id,
                symbol=symbol,
                decision="suppressed",
                reason="cooldown_active",
                signal_type=str(candidate_data["type"]),
                score=self._coerce_int(candidate_data.get("score")),
                suppressed=True,
                dedupe_key=dedupe_key,
            )
            return {"status": "suppressed", "dedupe_key": dedupe_key}

        signal_id = await self.persist_signal(session, candidate_data, dedupe_key=dedupe_key)
        recipient_ids = await self.resolve_recipients(
            session,
            symbol=symbol,
            score=float(candidate_data.get("score", 0) or 0),
        )
        await self.publish_signal_generated(
            session,
            signal_id=signal_id,
            candidate=candidate_data,
            recipient_ids=recipient_ids,
            dedupe_key=dedupe_key,
        )
        await self.record_decision(
            session,
            run_id=run_id,
            symbol=symbol,
            decision="emitted",
            reason="signal_generated",
            signal_type=str(candidate_data["type"]),
            score=self._coerce_int(candidate_data.get("score")),
            suppressed=False,
            dedupe_key=dedupe_key,
        )
        return {
            "status": "emitted",
            "signal_id": signal_id,
            "dedupe_key": dedupe_key,
            "recipient_count": len(recipient_ids),
        }

    async def list_scan_buckets(self) -> list[dict[str, Any]]:
        session = await self.open_session()
        try:
            from domains.signals.active_symbols_service import ActiveSymbolsService

            items = await ActiveSymbolsService(session).list_scan_buckets(self.bucket_count)
            return [self._normalize_bucket_item(item) for item in items]
        finally:
            await self.close_session(session)

    async def open_session(self) -> Any:
        from infra.db.session import get_session_factory

        session_factory = get_session_factory()
        return session_factory()

    async def close_session(self, session: Any) -> None:
        close = getattr(session, "close", None)
        if callable(close):
            result = close()
            if inspect.isawaitable(result):
                await result

    async def commit_session(self, session: Any) -> None:
        commit = getattr(session, "commit", None)
        if callable(commit):
            result = commit()
            if inspect.isawaitable(result):
                await result

    async def create_run(self, session: Any, bucket_id: int) -> Any:
        from domains.signals.repository import ScannerRunRepository

        return await ScannerRunRepository(session).create_run(bucket_id)

    async def finish_run(
        self,
        session: Any,
        run: Any,
        *,
        status: str,
        scanned_count: int,
        emitted_count: int,
        suppressed_count: int,
        error_message: str | None,
    ) -> Any:
        from domains.signals.repository import ScannerRunRepository

        return await ScannerRunRepository(session).finish_run(
            run,
            status=status,
            scanned_count=scanned_count,
            emitted_count=emitted_count,
            suppressed_count=suppressed_count,
            error_message=error_message,
        )

    async def record_decision(
        self,
        session: Any,
        *,
        run_id: int,
        symbol: str,
        decision: str,
        reason: str,
        signal_type: str | None,
        score: int | None,
        suppressed: bool,
        dedupe_key: str | None,
    ) -> Any:
        from domains.signals.repository import ScannerRunRepository
        from infra.events.outbox import OutboxPublisher

        record = await ScannerRunRepository(session).create_decision(
            run_id=run_id,
            symbol=symbol,
            decision=decision,
            reason=reason,
            signal_type=signal_type,
            score=score,
            suppressed=suppressed,
            dedupe_key=dedupe_key,
        )
        await OutboxPublisher(session).publish_after_commit(
            topic="scanner.decision.recorded",
            key=str(getattr(record, "id", "")),
            payload={
                "decision_id": getattr(record, "id", None),
                "run_id": run_id,
                "symbol": symbol,
                "decision": decision,
                "reason": reason,
                "signal_type": signal_type,
                "score": score,
                "suppressed": suppressed,
                "dedupe_key": dedupe_key,
            },
        )
        return record

    async def load_market_snapshot(
        self, symbol: str, session: Any, *, priority: int = 0
    ) -> dict[str, Any] | None:
        del priority
        if self.market_snapshot_provider is not None:
            result = self.market_snapshot_provider(symbol, session)
            if inspect.isawaitable(result):
                return await result
            return result

        from domains.market_data.repository import OhlcvRepository
        from domains.market_data.scanner_snapshot_service import ScannerSnapshotService

        bars = await OhlcvRepository(session).get_recent_bars(symbol, timeframe="1d", limit=60)
        return ScannerSnapshotService().build_snapshot(symbol, bars, timeframe="1d")

    async def find_recent_duplicate(
        self,
        session: Any,
        *,
        symbol: str,
        signal_type: str,
        dedupe_key: str,
    ) -> Any | None:
        from domains.signals.repository import SignalRepository

        return await SignalRepository(session).find_recent_duplicate(
            symbol=symbol,
            signal_type=signal_type,
            dedupe_key=dedupe_key,
            cooldown_minutes=self.cooldown_minutes,
        )

    async def persist_signal(
        self, session: Any, candidate: dict[str, Any], *, dedupe_key: str
    ) -> int:
        from domains.signals.repository import SignalRepository

        analysis = dict(candidate.get("analysis") or {})
        strategy_window = str(
            candidate.get("strategy_window") or analysis.get("strategy_window") or "default"
        )
        market_regime = str(
            candidate.get("market_regime") or analysis.get("market_regime") or "unknown"
        )
        signal = await SignalRepository(session).create_signal(
            {
                "symbol": candidate["symbol"],
                "signal_type": candidate["type"],
                "status": "pending",
                "entry_price": candidate["price"],
                "stop_loss": candidate.get("stop_loss"),
                "take_profit_1": candidate.get("take_profit_1"),
                "take_profit_2": candidate.get("take_profit_2"),
                "take_profit_3": candidate.get("take_profit_3"),
                "probability": candidate.get("probability") or analysis.get("probability") or 0,
                "confidence": candidate.get("confidence") or candidate.get("score") or 0,
                "risk_reward_ratio": candidate.get("risk_reward_ratio")
                or analysis.get("risk_reward_ratio"),
                "sfp_validated": bool(analysis.get("sfp_validated", False)),
                "chooch_validated": bool(analysis.get("chooch_validated", False)),
                "fvg_validated": bool(analysis.get("fvg_validated", False)),
                "validation_status": str(analysis.get("validation_status", "validated")),
                "atr_value": analysis.get("atr_value"),
                "atr_multiplier": analysis.get("atr_multiplier", 2.0),
                "reasoning": self._join_reasons(candidate.get("reasons") or []),
                "analysis": analysis,
                "source": "scanner.worker",
                "strategy_window": strategy_window,
                "market_regime": market_regime,
                "dedupe_key": dedupe_key,
                "generated_at": candidate.get("generated_at") or utcnow(),
            }
        )
        return int(getattr(signal, "id"))

    async def resolve_recipients(self, session: Any, *, symbol: str, score: float) -> list[int]:
        from domains.signals.audience_service import SignalAudienceResolver

        return await SignalAudienceResolver(session).resolve_recipient_ids(symbol, score)

    async def publish_signal_generated(
        self,
        session: Any,
        *,
        signal_id: int,
        candidate: dict[str, Any],
        recipient_ids: list[int],
        dedupe_key: str,
    ) -> None:
        from infra.events.outbox import OutboxPublisher

        analysis = dict(candidate.get("analysis") or {})
        strategy_window = str(
            candidate.get("strategy_window") or analysis.get("strategy_window") or "default"
        )
        market_regime = str(
            candidate.get("market_regime") or analysis.get("market_regime") or "unknown"
        )
        publisher = OutboxPublisher(session)
        await publisher.publish_after_commit(
            topic="signal.generated",
            key=str(signal_id),
            payload={
                "signal_id": str(signal_id),
                "symbol": candidate["symbol"],
                "signal_type": candidate["type"],
                "price": candidate["price"],
                "score": candidate.get("score"),
                "reasons": candidate.get("reasons") or [],
                "analysis": analysis,
                "source": "scanner.worker",
                "user_ids": recipient_ids,
                "strategy_window": strategy_window,
                "market_regime": market_regime,
                "dedupe_key": dedupe_key,
            },
        )
        await publisher.publish_after_commit(
            topic="ops.audit.logged",
            key=str(signal_id),
            payload={
                "entity": "signal",
                "entity_id": signal_id,
                "action": "scanner.generated",
                "source": "scanner.worker",
                "symbol": candidate["symbol"],
                "signal_type": candidate["type"],
            },
        )

    def stop(self) -> None:
        self._running = False

    @staticmethod
    def _candidate_to_dict(candidate: Any) -> dict[str, Any]:
        if hasattr(candidate, "model_dump"):
            return dict(candidate.model_dump())
        if isinstance(candidate, dict):
            return dict(candidate)
        raise TypeError("Unsupported candidate type")

    @staticmethod
    def _normalize_bucket_item(item: Any) -> dict[str, Any]:
        if hasattr(item, "model_dump"):
            data = item.model_dump()
        elif isinstance(item, dict):
            data = dict(item)
        else:
            data = {
                "bucket_id": int(getattr(item, "bucket_id")),
                "symbol": str(getattr(item, "symbol")),
                "priority": int(getattr(item, "priority", 0)),
            }
        return {
            "bucket_id": int(data["bucket_id"]),
            "symbol": str(data["symbol"]).upper(),
            "priority": int(data.get("priority", 0)),
        }

    @staticmethod
    def _join_reasons(reasons: list[str]) -> str | None:
        items = [str(reason).strip() for reason in reasons if str(reason).strip()]
        return "; ".join(items) if items else None

    @staticmethod
    def _extract_run_id(run: Any) -> int:
        return int(getattr(run, "id", run))

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    result = await run_runtime_monitored(
        "scanner",
        "worker",
        ScannerWorker().run_once,
        metadata={"mode": "batch"},
        final_status="completed",
    )
    logger.info("Scanner cycle finished: %s", result)


if __name__ == "__main__":
    asyncio.run(main())
