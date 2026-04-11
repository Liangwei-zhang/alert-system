from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Iterable

from infra.observability.runtime_monitoring import run_runtime_monitored

logger = logging.getLogger(__name__)


class BacktestWorker:
    def __init__(
        self,
        *,
        poll_interval_seconds: int = 3600,
        timeframe: str = "1d",
        windows: Iterable[int] = (30, 90, 180, 365),
        service_factory: Any | None = None,
    ) -> None:
        self.poll_interval = poll_interval_seconds
        self.timeframe = timeframe
        self.windows = tuple(int(window) for window in windows)
        self.service_factory = service_factory
        self._running = False

    async def run_forever(self, initial_delay: float = 5.0) -> None:
        logger.info("Starting backtest worker")
        await asyncio.sleep(initial_delay)
        self._running = True
        while self._running:
            try:
                await self.refresh_rankings()
            except Exception:
                logger.exception("Backtest worker cycle failed")
            await asyncio.sleep(self.poll_interval)
        logger.info("Backtest worker stopped")

    async def refresh_rankings(
        self,
        *,
        symbols: list[str] | None = None,
        strategy_names: list[str] | None = None,
    ) -> dict[str, Any]:
        session = await self.open_session()
        try:
            service = self.build_service(session)
            result = await service.refresh_rankings(
                symbols=symbols,
                strategy_names=strategy_names,
                windows=self.windows,
                timeframe=self.timeframe,
                experiment_name="scheduler.backtest-refresh",
                experiment_context={
                    "trigger": "scheduler",
                    "entrypoint": "apps.workers.backtest.worker.BacktestWorker.refresh_rankings",
                    "poll_interval_seconds": self.poll_interval,
                    "dataset": {
                        "selection_mode": "active_symbols",
                    },
                },
            )
            await self.commit_session(session)
            return result
        finally:
            await self.close_session(session)

    def build_service(self, session: Any) -> Any:
        if self.service_factory is not None:
            return self.service_factory(session)
        from domains.analytics.backtest.service import BacktestService

        return BacktestService(session)

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

    def stop(self) -> None:
        self._running = False


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    result = await run_runtime_monitored(
        "backtest",
        "worker",
        BacktestWorker().refresh_rankings,
        metadata={"mode": "batch"},
        final_status="completed",
    )
    logger.info("Backtest refresh finished: %s", result)


if __name__ == "__main__":
    asyncio.run(main())
