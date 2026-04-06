from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from domains.notifications.retention_service import (
    RetentionMaintenanceResult,
    RetentionMaintenanceService,
)
from infra.core.config import get_settings
from infra.observability.runtime_monitoring import run_runtime_monitored

logger = logging.getLogger(__name__)


class RetentionMaintenanceWorker:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Any] | None = None,
        service_factory: Callable[[Any], RetentionMaintenanceService] | None = None,
        poll_interval_seconds: float | None = None,
        drain_interval_seconds: float = 5.0,
    ) -> None:
        settings = get_settings()
        self.session_factory = session_factory
        self.service_factory = service_factory
        self.poll_interval_seconds = max(
            float(
                settings.retention_worker_poll_seconds
                if poll_interval_seconds is None
                else poll_interval_seconds
            ),
            60.0,
        )
        self.drain_interval_seconds = max(float(drain_interval_seconds), 1.0)
        self._running = False

    async def run_forever(self) -> None:
        self._running = True
        while self._running:
            try:
                result = RetentionMaintenanceResult(**await self.run_once())
                await asyncio.sleep(self.next_delay_seconds(result))
            except Exception:
                logger.exception("Retention maintenance cycle failed")
                await asyncio.sleep(self.poll_interval_seconds)

    async def run_once(self) -> dict[str, Any]:
        session = await self.open_session()
        try:
            service = self.build_service(session)
            result = await service.run_once()
            await self.commit_session(session)
            return result.to_dict()
        finally:
            await self.close_session(session)

    def stop(self) -> None:
        self._running = False

    def build_service(self, session: Any) -> RetentionMaintenanceService:
        if self.service_factory is not None:
            return self.service_factory(session)
        return RetentionMaintenanceService(session)

    async def open_session(self) -> Any:
        if self.session_factory is None:
            from infra.db.session import get_session_factory

            self.session_factory = get_session_factory()
        return self.session_factory()

    async def commit_session(self, session: Any) -> None:
        commit = getattr(session, "commit", None)
        if callable(commit):
            result = commit()
            if hasattr(result, "__await__"):
                await result

    async def close_session(self, session: Any) -> None:
        close = getattr(session, "close", None)
        if callable(close):
            result = close()
            if hasattr(result, "__await__"):
                await result

    def next_delay_seconds(self, result: RetentionMaintenanceResult) -> float:
        if not result.lock_acquired:
            return self.poll_interval_seconds
        if result.did_work:
            return self.drain_interval_seconds
        return self.poll_interval_seconds


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    worker = RetentionMaintenanceWorker()
    await run_runtime_monitored(
        "retention",
        "worker",
        worker.run_forever,
        metadata={"mode": "continuous"},
        heartbeat_interval_seconds=max(worker.poll_interval_seconds / 2, 5),
        ttl_seconds=max(int(worker.poll_interval_seconds * 3), 30),
        final_status="stopped",
    )


if __name__ == "__main__":
    asyncio.run(main())
