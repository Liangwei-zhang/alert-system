from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from domains.signals.calibration_service import CalibrationService
from infra.db.models.signals import SignalCalibrationSnapshotModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SignalCalibrationSnapshotRepository:
    def __init__(
        self,
        session: AsyncSession,
        calibration_service: CalibrationService | None = None,
    ) -> None:
        self.session = session
        self.calibration_service = calibration_service or CalibrationService()

    async def list_snapshots(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        statement = select(SignalCalibrationSnapshotModel)
        if active_only:
            statement = statement.where(SignalCalibrationSnapshotModel.is_active.is_(True))
        result = await self.session.execute(
            statement
            .order_by(
                SignalCalibrationSnapshotModel.is_active.desc(),
                func.coalesce(
                    SignalCalibrationSnapshotModel.effective_from,
                    SignalCalibrationSnapshotModel.effective_at,
                )
                .desc()
                .nullslast(),
                SignalCalibrationSnapshotModel.created_at.desc(),
                SignalCalibrationSnapshotModel.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return [self._serialize_model(model) for model in result.scalars().all()]

    async def count_snapshots(self, *, active_only: bool = False) -> int:
        statement = select(func.count(SignalCalibrationSnapshotModel.id))
        if active_only:
            statement = statement.where(SignalCalibrationSnapshotModel.is_active.is_(True))
        result = await self.session.execute(statement)
        return int(result.scalar_one() or 0)

    async def get_active_snapshot(self) -> dict[str, Any] | None:
        result = await self.session.execute(
            select(SignalCalibrationSnapshotModel)
            .where(SignalCalibrationSnapshotModel.is_active.is_(True))
            .order_by(
                func.coalesce(
                    SignalCalibrationSnapshotModel.effective_from,
                    SignalCalibrationSnapshotModel.effective_at,
                )
                .desc()
                .nullslast(),
                SignalCalibrationSnapshotModel.created_at.desc(),
                SignalCalibrationSnapshotModel.id.desc(),
            )
            .limit(1)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._serialize_model(model)

    async def activate_snapshot(self, snapshot_id: int) -> dict[str, Any]:
        result = await self.session.execute(
            select(SignalCalibrationSnapshotModel).where(
                SignalCalibrationSnapshotModel.id == int(snapshot_id)
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ValueError("Calibration snapshot not found")

        now = utcnow()
        await self.session.execute(
            update(SignalCalibrationSnapshotModel)
            .where(SignalCalibrationSnapshotModel.is_active.is_(True))
            .values(is_active=False)
        )
        model.is_active = True
        model.effective_from = now
        model.effective_at = now
        await self.session.flush()
        return self._serialize_model(model)

    async def create_snapshot(
        self,
        *,
        version: str,
        source: str = "manual_review",
        strategy_weights: dict[str, Any] | None = None,
        score_multipliers: dict[str, Any] | None = None,
        atr_multipliers: dict[str, Any] | None = None,
        derived_from: str | None = None,
        sample_size: int | None = None,
        activate: bool = False,
        effective_from: datetime | None = None,
        effective_at: datetime | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        resolved_effective_from = effective_from or effective_at
        normalized = self.calibration_service.normalize_snapshot(
            {
                "version": version,
                "source": source,
                "effective_from": resolved_effective_from,
                "strategy_weights": dict(strategy_weights or {}),
                "score_multipliers": dict(score_multipliers or {}),
                "atr_multipliers": dict(atr_multipliers or {}),
            }
        )

        existing_result = await self.session.execute(
            select(SignalCalibrationSnapshotModel.id).where(
                SignalCalibrationSnapshotModel.version == normalized.version
            )
        )
        if existing_result.scalar_one_or_none() is not None:
            raise ValueError(f"Calibration snapshot version '{normalized.version}' already exists")

        if activate:
            await self.session.execute(
                update(SignalCalibrationSnapshotModel)
                .where(SignalCalibrationSnapshotModel.is_active.is_(True))
                .values(is_active=False)
            )

        applied_effective_from = normalized.effective_from or (utcnow() if activate else None)

        model = SignalCalibrationSnapshotModel(
            version=normalized.version,
            source=normalized.source,
            snapshot=json.dumps(
                self.calibration_service.snapshot_payload(normalized),
                sort_keys=True,
            ),
            derived_from=(str(derived_from).strip() if derived_from else None),
            sample_size=sample_size,
            is_active=bool(activate),
            effective_from=applied_effective_from,
            effective_at=applied_effective_from,
            notes=(str(notes).strip() if notes else None),
        )
        self.session.add(model)
        await self.session.flush()
        return self._serialize_model(model)

    def _serialize_model(self, model: SignalCalibrationSnapshotModel) -> dict[str, Any]:
        payload = self._load_payload(getattr(model, "snapshot", None))
        payload.setdefault("version", getattr(model, "version", None))
        payload.setdefault("source", getattr(model, "source", None))
        snapshot = self.calibration_service.normalize_snapshot(payload)
        effective_from = getattr(model, "effective_from", None) or snapshot.effective_from
        return {
            "id": int(model.id),
            "version": snapshot.version,
            "source": snapshot.source,
            "strategy_weights": dict(snapshot.strategy_weights),
            "score_multipliers": dict(snapshot.score_multipliers),
            "atr_multipliers": dict(snapshot.atr_multipliers),
            "derived_from": getattr(model, "derived_from", None),
            "sample_size": getattr(model, "sample_size", None),
            "is_active": bool(getattr(model, "is_active", False)),
            "effective_from": effective_from,
            "effective_at": getattr(model, "effective_at", None),
            "notes": getattr(model, "notes", None),
            "created_at": getattr(model, "created_at", None),
            "updated_at": getattr(model, "updated_at", None),
        }

    @staticmethod
    def _load_payload(value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            payload = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}