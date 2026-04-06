from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.db.models.signals import (
    ScannerDecisionModel,
    ScannerRunModel,
    SignalModel,
    SignalStatus,
    SignalType,
    SignalValidation,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SignalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_admin_signals(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        signal_type: str | None = None,
        symbol: str | None = None,
        validation_status: str | None = None,
    ) -> list[SignalModel]:
        statement = select(SignalModel)
        filters = self._admin_signal_filters(
            status=status,
            signal_type=signal_type,
            symbol=symbol,
            validation_status=validation_status,
        )
        if filters:
            statement = statement.where(*filters)
        result = await self.session.execute(
            statement.order_by(SignalModel.generated_at.desc(), SignalModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_admin_signals(
        self,
        *,
        status: str | None = None,
        signal_type: str | None = None,
        symbol: str | None = None,
        validation_status: str | None = None,
    ) -> int:
        return await self._count_filtered_signals(
            status=status,
            signal_type=signal_type,
            symbol=symbol,
            validation_status=validation_status,
        )

    async def summarize_admin_signals(self, *, window_hours: int = 24 * 7) -> dict[str, Any]:
        generated_after = utcnow() - timedelta(hours=window_hours)
        filters = self._admin_signal_filters(generated_after=generated_after)

        top_symbols_statement = (
            select(SignalModel.symbol, func.count(SignalModel.id).label("count"))
            .group_by(SignalModel.symbol)
            .order_by(func.count(SignalModel.id).desc(), SignalModel.symbol.asc())
            .limit(5)
        )
        if filters:
            top_symbols_statement = top_symbols_statement.where(*filters)
        top_symbols_result = await self.session.execute(top_symbols_statement)

        averages_statement = select(
            func.avg(SignalModel.probability),
            func.avg(SignalModel.confidence),
        )
        if filters:
            averages_statement = averages_statement.where(*filters)
        averages_result = await self.session.execute(averages_statement)
        avg_probability, avg_confidence = averages_result.one()

        return {
            "window_hours": int(window_hours),
            "generated_after": generated_after,
            "total_signals": await self._count_filtered_signals(generated_after=generated_after),
            "pending_signals": await self._count_filtered_signals(
                generated_after=generated_after,
                status=SignalStatus.PENDING.value,
            ),
            "active_signals": await self._count_filtered_signals(
                generated_after=generated_after,
                status=SignalStatus.ACTIVE.value,
            ),
            "triggered_signals": await self._count_filtered_signals(
                generated_after=generated_after,
                status=SignalStatus.TRIGGERED.value,
            ),
            "expired_signals": await self._count_filtered_signals(
                generated_after=generated_after,
                status=SignalStatus.EXPIRED.value,
            ),
            "cancelled_signals": await self._count_filtered_signals(
                generated_after=generated_after,
                status=SignalStatus.CANCELLED.value,
            ),
            "buy_signals": await self._count_filtered_signals(
                generated_after=generated_after,
                signal_type=SignalType.BUY.value,
            ),
            "sell_signals": await self._count_filtered_signals(
                generated_after=generated_after,
                signal_type=SignalType.SELL.value,
            ),
            "split_buy_signals": await self._count_filtered_signals(
                generated_after=generated_after,
                signal_type=SignalType.SPLIT_BUY.value,
            ),
            "split_sell_signals": await self._count_filtered_signals(
                generated_after=generated_after,
                signal_type=SignalType.SPLIT_SELL.value,
            ),
            "avg_probability": round(float(avg_probability or 0.0), 4),
            "avg_confidence": round(float(avg_confidence or 0.0), 4),
            "top_symbols": [
                {"symbol": str(symbol), "count": int(count or 0)}
                for symbol, count in top_symbols_result.all()
            ],
        }

    async def create_signal(self, payload: dict[str, Any]) -> SignalModel:
        metadata = dict(payload.get("analysis") or {})
        metadata.update(
            {
                "source": payload.get("source"),
                "emitted_at": payload.get("emitted_at"),
                "strategy_window": payload.get("strategy_window"),
                "market_regime": payload.get("market_regime"),
                "dedupe_key": payload.get("dedupe_key"),
            }
        )
        signal = SignalModel(
            stock_id=payload.get("stock_id"),
            symbol=str(payload["symbol"]).upper(),
            signal_type=SignalType(str(payload["signal_type"]).lower()),
            status=SignalStatus(str(payload.get("status", SignalStatus.PENDING.value)).lower()),
            entry_price=float(payload["entry_price"]),
            stop_loss=payload.get("stop_loss"),
            take_profit_1=payload.get("take_profit_1"),
            take_profit_2=payload.get("take_profit_2"),
            take_profit_3=payload.get("take_profit_3"),
            probability=float(payload.get("probability", 0) or 0),
            confidence=float(payload.get("confidence", 0) or 0),
            risk_reward_ratio=payload.get("risk_reward_ratio"),
            sfp_validated=bool(payload.get("sfp_validated", False)),
            chooch_validated=bool(payload.get("chooch_validated", False)),
            fvg_validated=bool(payload.get("fvg_validated", False)),
            validation_status=SignalValidation(
                str(payload.get("validation_status", SignalValidation.VALIDATED.value)).lower()
            ),
            atr_value=payload.get("atr_value"),
            atr_multiplier=float(payload.get("atr_multiplier", 2.0) or 2.0),
            indicators=json.dumps(metadata, default=str) if metadata else None,
            reasoning=payload.get("reasoning"),
            generated_at=payload.get("generated_at") or utcnow(),
        )
        self.session.add(signal)
        await self.session.flush()
        return signal

    async def find_recent_duplicate(
        self,
        symbol: str,
        signal_type: str,
        dedupe_key: str,
        cooldown_minutes: int = 60,
    ) -> SignalModel | None:
        cutoff = utcnow() - timedelta(minutes=cooldown_minutes)
        result = await self.session.execute(
            select(SignalModel)
            .where(
                SignalModel.symbol == symbol.upper(),
                SignalModel.signal_type == SignalType(signal_type.lower()),
                SignalModel.generated_at >= cutoff,
            )
            .order_by(SignalModel.generated_at.desc(), SignalModel.id.desc())
            .limit(25)
        )
        for signal in result.scalars().all():
            metadata = self._load_metadata(signal)
            if metadata.get("dedupe_key") == dedupe_key:
                return signal
        return None

    async def list_recent_by_symbol(self, symbol: str, limit: int = 20) -> list[SignalModel]:
        result = await self.session.execute(
            select(SignalModel)
            .where(SignalModel.symbol == symbol.upper())
            .order_by(SignalModel.generated_at.desc(), SignalModel.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _count_filtered_signals(
        self,
        *,
        generated_after: datetime | None = None,
        status: str | None = None,
        signal_type: str | None = None,
        symbol: str | None = None,
        validation_status: str | None = None,
    ) -> int:
        statement = select(func.count()).select_from(SignalModel)
        filters = self._admin_signal_filters(
            generated_after=generated_after,
            status=status,
            signal_type=signal_type,
            symbol=symbol,
            validation_status=validation_status,
        )
        if filters:
            statement = statement.where(*filters)
        result = await self.session.execute(statement)
        return int(result.scalar_one() or 0)

    @staticmethod
    def _admin_signal_filters(
        *,
        generated_after: datetime | None = None,
        status: str | None = None,
        signal_type: str | None = None,
        symbol: str | None = None,
        validation_status: str | None = None,
    ) -> list[Any]:
        filters: list[Any] = []
        if generated_after is not None:
            filters.append(SignalModel.generated_at >= generated_after)
        if status:
            filters.append(SignalModel.status == SignalStatus(status.lower()))
        if signal_type:
            filters.append(SignalModel.signal_type == SignalType(signal_type.lower()))
        if symbol:
            filters.append(SignalModel.symbol == symbol.strip().upper())
        if validation_status:
            filters.append(
                SignalModel.validation_status == SignalValidation(validation_status.lower())
            )
        return filters

    @staticmethod
    def _load_metadata(signal: SignalModel) -> dict[str, Any]:
        if not signal.indicators:
            return {}
        try:
            payload = json.loads(signal.indicators)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}


class ScannerRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_runs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        bucket_id: int | None = None,
    ) -> list[ScannerRunModel]:
        statement = select(ScannerRunModel)
        if status:
            statement = statement.where(ScannerRunModel.status == status.strip().lower())
        if bucket_id is not None:
            statement = statement.where(ScannerRunModel.bucket_id == bucket_id)
        result = await self.session.execute(
            statement.order_by(ScannerRunModel.started_at.desc(), ScannerRunModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_runs(
        self,
        *,
        status: str | None = None,
        bucket_id: int | None = None,
    ) -> int:
        statement = select(func.count()).select_from(ScannerRunModel)
        if status:
            statement = statement.where(ScannerRunModel.status == status.strip().lower())
        if bucket_id is not None:
            statement = statement.where(ScannerRunModel.bucket_id == bucket_id)
        result = await self.session.execute(statement)
        return int(result.scalar_one() or 0)

    async def get_run(self, run_id: int) -> ScannerRunModel | None:
        result = await self.session.execute(
            select(ScannerRunModel).where(ScannerRunModel.id == run_id)
        )
        return result.scalar_one_or_none()

    async def list_decisions(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        run_id: int | None = None,
        symbol: str | None = None,
        decision: str | None = None,
        suppressed: bool | None = None,
    ) -> list[ScannerDecisionModel]:
        statement = select(ScannerDecisionModel)
        if run_id is not None:
            statement = statement.where(ScannerDecisionModel.run_id == run_id)
        if symbol:
            statement = statement.where(ScannerDecisionModel.symbol == symbol.strip().upper())
        if decision:
            statement = statement.where(ScannerDecisionModel.decision == decision.strip().lower())
        if suppressed is not None:
            statement = statement.where(ScannerDecisionModel.suppressed == suppressed)
        result = await self.session.execute(
            statement.order_by(
                ScannerDecisionModel.created_at.desc(), ScannerDecisionModel.id.desc()
            )
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_decisions(
        self,
        *,
        run_id: int | None = None,
        symbol: str | None = None,
        decision: str | None = None,
        suppressed: bool | None = None,
    ) -> int:
        statement = select(func.count()).select_from(ScannerDecisionModel)
        if run_id is not None:
            statement = statement.where(ScannerDecisionModel.run_id == run_id)
        if symbol:
            statement = statement.where(ScannerDecisionModel.symbol == symbol.strip().upper())
        if decision:
            statement = statement.where(ScannerDecisionModel.decision == decision.strip().lower())
        if suppressed is not None:
            statement = statement.where(ScannerDecisionModel.suppressed == suppressed)
        result = await self.session.execute(statement)
        return int(result.scalar_one() or 0)

    async def create_run(self, bucket_id: int) -> ScannerRunModel:
        run = ScannerRunModel(bucket_id=bucket_id)
        self.session.add(run)
        await self.session.flush()
        return run

    async def finish_run(
        self,
        run: ScannerRunModel,
        *,
        status: str,
        scanned_count: int,
        emitted_count: int,
        suppressed_count: int,
        error_message: str | None = None,
    ) -> ScannerRunModel:
        run.status = status
        run.scanned_count = scanned_count
        run.emitted_count = emitted_count
        run.suppressed_count = suppressed_count
        run.error_message = error_message
        run.finished_at = utcnow()
        await self.session.flush()
        return run

    async def create_decision(
        self,
        *,
        run_id: int,
        symbol: str,
        decision: str,
        reason: str,
        signal_type: str | None = None,
        score: float | None = None,
        suppressed: bool = False,
        dedupe_key: str | None = None,
    ) -> ScannerDecisionModel:
        record = ScannerDecisionModel(
            run_id=run_id,
            symbol=symbol.upper(),
            decision=decision,
            reason=reason,
            signal_type=signal_type,
            score=score,
            suppressed=suppressed,
            dedupe_key=dedupe_key,
        )
        self.session.add(record)
        await self.session.flush()
        return record
