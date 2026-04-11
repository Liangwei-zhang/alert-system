from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.db.models.backtest import BacktestRunModel, BacktestRunStatus, StrategyRankingModel
from infra.db.models.market_data import OhlcvModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BacktestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_runs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        strategy_name: str | None = None,
        experiment_name: str | None = None,
        run_key: str | None = None,
        timeframe: str | None = None,
        symbol: str | None = None,
    ) -> list[BacktestRunModel]:
        statement = select(BacktestRunModel)
        if status:
            statement = statement.where(
                BacktestRunModel.status == BacktestRunStatus(status.lower())
            )
        if strategy_name:
            statement = statement.where(BacktestRunModel.strategy_name == strategy_name.strip())
        if experiment_name:
            statement = statement.where(
                BacktestRunModel.experiment_name == experiment_name.strip()
            )
        if run_key:
            statement = statement.where(BacktestRunModel.run_key == run_key.strip())
        if timeframe:
            statement = statement.where(BacktestRunModel.timeframe == timeframe.strip().lower())
        if symbol:
            statement = statement.where(BacktestRunModel.symbol == symbol.strip().upper())
        result = await self.session.execute(
            statement.order_by(BacktestRunModel.started_at.desc(), BacktestRunModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_runs(
        self,
        *,
        status: str | None = None,
        strategy_name: str | None = None,
        experiment_name: str | None = None,
        run_key: str | None = None,
        timeframe: str | None = None,
        symbol: str | None = None,
    ) -> int:
        statement = select(func.count()).select_from(BacktestRunModel)
        if status:
            statement = statement.where(
                BacktestRunModel.status == BacktestRunStatus(status.lower())
            )
        if strategy_name:
            statement = statement.where(BacktestRunModel.strategy_name == strategy_name.strip())
        if experiment_name:
            statement = statement.where(
                BacktestRunModel.experiment_name == experiment_name.strip()
            )
        if run_key:
            statement = statement.where(BacktestRunModel.run_key == run_key.strip())
        if timeframe:
            statement = statement.where(BacktestRunModel.timeframe == timeframe.strip().lower())
        if symbol:
            statement = statement.where(BacktestRunModel.symbol == symbol.strip().upper())
        result = await self.session.execute(statement)
        return int(result.scalar_one() or 0)

    async def get_run(self, run_id: int) -> BacktestRunModel | None:
        return await self._get_run(run_id)

    async def list_latest_rankings(
        self,
        *,
        timeframe: str | None = None,
        limit: int = 20,
    ) -> list[StrategyRankingModel]:
        latest_statement = select(func.max(StrategyRankingModel.as_of_date))
        if timeframe:
            latest_statement = latest_statement.where(
                StrategyRankingModel.timeframe == timeframe.strip().lower()
            )
        latest_result = await self.session.execute(latest_statement)
        latest_as_of = latest_result.scalar_one_or_none()
        if latest_as_of is None:
            return []

        statement = select(StrategyRankingModel).where(
            StrategyRankingModel.as_of_date == latest_as_of
        )
        if timeframe:
            statement = statement.where(StrategyRankingModel.timeframe == timeframe.strip().lower())
        result = await self.session.execute(
            statement.order_by(
                StrategyRankingModel.rank.asc(), StrategyRankingModel.id.asc()
            ).limit(limit)
        )
        return list(result.scalars().all())

    async def save_run(self, payload: dict[str, Any]) -> BacktestRunModel:
        record = BacktestRunModel(
            strategy_name=str(payload.get("strategy_name") or "ranking_refresh"),
            experiment_name=payload.get("experiment_name"),
            run_key=payload.get("run_key"),
            symbol=payload.get("symbol"),
            timeframe=str(payload.get("timeframe") or "1d"),
            window_days=int(payload.get("window_days") or 0),
            status=BacktestRunStatus(
                str(payload.get("status") or BacktestRunStatus.PENDING.value).lower()
            ),
            summary=self._dump(payload.get("summary")),
            config=self._dump(payload.get("config")),
            metrics=self._dump(payload.get("metrics")),
            evidence=self._dump(payload.get("evidence")),
            artifacts=self._dump(payload.get("artifacts")),
            code_version=payload.get("code_version"),
            dataset_fingerprint=payload.get("dataset_fingerprint"),
            error_message=payload.get("error_message"),
            started_at=payload.get("started_at") or utcnow(),
            completed_at=payload.get("completed_at"),
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def save_results(
        self, run: BacktestRunModel | int, results: dict[str, Any]
    ) -> BacktestRunModel:
        record = run if isinstance(run, BacktestRunModel) else await self._get_run(int(run))
        if record is None:
            raise ValueError("backtest run not found")
        if results.get("status") is not None:
            record.status = BacktestRunStatus(str(results["status"]).lower())
        if "summary" in results:
            record.summary = self._dump(results.get("summary"))
        if "config" in results:
            record.config = self._dump(results.get("config"))
        if "metrics" in results:
            record.metrics = self._dump(results.get("metrics"))
        if "evidence" in results:
            record.evidence = self._dump(results.get("evidence"))
        if "artifacts" in results:
            record.artifacts = self._dump(results.get("artifacts"))
        if "code_version" in results:
            record.code_version = results.get("code_version")
        if "dataset_fingerprint" in results:
            record.dataset_fingerprint = results.get("dataset_fingerprint")
        if "error_message" in results:
            record.error_message = results.get("error_message")
        if record.status in {BacktestRunStatus.COMPLETED, BacktestRunStatus.FAILED}:
            record.completed_at = results.get("completed_at") or utcnow()
        await self.session.flush()
        return record

    async def save_rankings(
        self,
        rankings: list[dict[str, Any]],
        *,
        as_of_date: datetime | None = None,
    ) -> list[StrategyRankingModel]:
        timestamp = as_of_date or utcnow()
        saved: list[StrategyRankingModel] = []
        for ranking in rankings:
            record = StrategyRankingModel(
                strategy_name=str(ranking["strategy_name"]),
                timeframe=str(ranking.get("timeframe") or "1d"),
                rank=int(ranking.get("rank") or 0),
                score=float(ranking.get("score") or 0.0),
                degradation=float(ranking.get("degradation") or 0.0),
                symbols_covered=int(ranking.get("symbols_covered") or 0),
                evidence=self._dump(ranking.get("evidence")),
                as_of_date=timestamp,
            )
            self.session.add(record)
            saved.append(record)
        await self.session.flush()
        return saved

    async def load_window_data(
        self,
        symbol: str,
        window_days: int,
        timeframe: str = "1d",
    ) -> list[dict[str, Any]]:
        normalized_symbol = symbol.strip().upper()
        normalized_timeframe = timeframe.strip().lower()
        latest_bar_result = await self.session.execute(
            select(func.max(OhlcvModel.bar_time)).where(
                OhlcvModel.symbol == normalized_symbol,
                OhlcvModel.timeframe == normalized_timeframe,
            )
        )
        latest_bar_time = latest_bar_result.scalar_one_or_none()
        if latest_bar_time is None:
            return []

        cutoff = latest_bar_time - timedelta(days=window_days)
        result = await self.session.execute(
            select(OhlcvModel)
            .where(
                OhlcvModel.symbol == normalized_symbol,
                OhlcvModel.timeframe == normalized_timeframe,
                OhlcvModel.bar_time >= cutoff,
                OhlcvModel.bar_time <= latest_bar_time,
            )
            .order_by(OhlcvModel.bar_time.asc())
        )
        rows = list(result.scalars().all())
        return [
            {
                "timestamp": row.bar_time,
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": float(row.volume),
                "symbol": row.symbol,
                "timeframe": row.timeframe,
            }
            for row in rows
        ]

    async def _get_run(self, run_id: int) -> BacktestRunModel | None:
        result = await self.session.execute(
            select(BacktestRunModel).where(BacktestRunModel.id == run_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _dump(value: Any) -> str | None:
        if value in (None, "", [], {}):
            return None
        return json.dumps(value, default=str)
