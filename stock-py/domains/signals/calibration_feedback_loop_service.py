from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from domains.analytics.repository import AnalyticsRepository
from domains.signals.calibration_proposal_service import CalibrationProposalService
from domains.signals.calibration_repository import SignalCalibrationSnapshotRepository


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CalibrationFeedbackLoopService:
    def __init__(
        self,
        *,
        analytics_repository: AnalyticsRepository,
        calibration_repository: SignalCalibrationSnapshotRepository,
    ) -> None:
        self.analytics_repository = analytics_repository
        self.calibration_repository = calibration_repository

    async def create_feedback_snapshot(
        self,
        *,
        run_id: int | None,
        timeframe: str,
        signal_window_hours: int = 24,
        ranking_window_hours: int = 24 * 7,
        activate: bool = True,
        experiment_name: str | None = None,
    ) -> dict[str, Any]:
        proposal = await CalibrationProposalService(
            analytics_repository=self.analytics_repository,
            calibration_repository=self.calibration_repository,
        ).build_proposal(
            signal_window_hours=signal_window_hours,
            ranking_window_hours=ranking_window_hours,
        )
        snapshot_payload = dict(proposal.get("snapshot_payload") or {})
        effective_from = utcnow()
        version = self._feedback_version(effective_from, run_id=run_id)
        notes = [
            str(snapshot_payload.get("notes") or "").strip(),
            f"auto feedback loop from backtest refresh {run_id}" if run_id is not None else "auto feedback loop from backtest refresh",
            f"timeframe={timeframe}",
        ]
        derived_from_parts = [
            str(snapshot_payload.get("derived_from") or "").strip(),
            f"backtest-run:{run_id}" if run_id is not None else "",
            f"timeframe:{timeframe}",
            f"experiment:{experiment_name}" if experiment_name else "",
        ]
        snapshot = await self.calibration_repository.create_snapshot(
            version=version,
            source="backtest_feedback_loop",
            strategy_weights=dict(snapshot_payload.get("strategy_weights") or {}),
            score_multipliers=dict(snapshot_payload.get("score_multipliers") or {}),
            atr_multipliers=dict(snapshot_payload.get("atr_multipliers") or {}),
            derived_from="; ".join(part for part in derived_from_parts if part),
            sample_size=int(snapshot_payload.get("sample_size") or 0),
            activate=activate,
            effective_from=effective_from,
            notes="; ".join(part for part in notes if part),
        )
        return {
            "generated_at": effective_from,
            "applied_version": snapshot.get("version"),
            "previous_version": proposal.get("current_version"),
            "activated": bool(snapshot.get("is_active", False)),
            "effective_from": snapshot.get("effective_from") or snapshot.get("effective_at"),
            "strategy_weights": dict(snapshot.get("strategy_weights") or {}),
            "score_multipliers": dict(snapshot.get("score_multipliers") or {}),
            "atr_multipliers": dict(snapshot.get("atr_multipliers") or {}),
            "notes": list(proposal.get("notes") or []),
            "snapshot": snapshot,
        }

    @staticmethod
    def _feedback_version(generated_at: datetime, *, run_id: int | None) -> str:
        suffix = f"-r{run_id}" if run_id is not None else ""
        return f"signals-v2-feedback-{generated_at:%Y%m%dT%H%M%SZ}{suffix}"