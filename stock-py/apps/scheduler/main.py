from __future__ import annotations

import asyncio
import inspect
import logging
import signal
from typing import Any, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from apps.workers.backtest.worker import BacktestWorker
from apps.workers.cold_storage.worker import ColdStorageWorker
from apps.workers.email_dispatch.worker import EmailDispatchWorker
from apps.workers.event_pipeline.worker import BrokerDispatchWorker, EventOutboxRelayWorker
from apps.workers.market_data.worker import MarketDataWorker
from apps.workers.push_dispatch.worker import PushDispatchWorker
from apps.workers.receipt_escalation.worker import ReceiptEscalationWorker
from apps.workers.retention.worker import RetentionMaintenanceWorker
from apps.workers.scanner.worker import ScannerWorker
from apps.workers.tradingagents_bridge.worker import TradingAgentsPollingWorker
from infra.core.config import get_settings
from infra.core.logging import configure_logging
from infra.observability.runtime_monitoring import run_runtime_monitored
from infra.observability.tracing import configure_tracing

logger = logging.getLogger(__name__)


async def _run_scheduled_job(job_id: str, callable_: Callable[[], Any]) -> Any:
    result = callable_()
    if inspect.isawaitable(result):
        result = await result
    logger.info("scheduler_job_completed job_id=%s result=%s", job_id, result)
    return result


def _register_interval_job(
    scheduler: AsyncIOScheduler,
    *,
    job_id: str,
    callable_: Callable[[], Any],
    seconds: float,
) -> None:
    scheduler.add_job(
        _run_scheduled_job,
        trigger="interval",
        seconds=max(float(seconds), 1.0),
        id=job_id,
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=max(int(max(float(seconds), 1.0) * 2), 5),
        args=[job_id, callable_],
    )


def build_scheduler() -> AsyncIOScheduler:
    settings = get_settings()
    scheduler = AsyncIOScheduler(timezone="UTC")

    def heartbeat() -> None:
        logger.info("scheduler_heartbeat")

    retention_worker = RetentionMaintenanceWorker()
    backtest_worker = BacktestWorker()
    market_data_worker = MarketDataWorker()
    scanner_worker = ScannerWorker()
    receipt_escalation_worker = ReceiptEscalationWorker()
    cold_storage_worker = ColdStorageWorker()
    tradingagents_worker = TradingAgentsPollingWorker()
    event_relay_worker = EventOutboxRelayWorker()
    broker_dispatch_worker = BrokerDispatchWorker()
    push_dispatch_worker = PushDispatchWorker()
    email_dispatch_worker = EmailDispatchWorker()

    _register_interval_job(
        scheduler,
        job_id="scheduler-heartbeat",
        callable_=heartbeat,
        seconds=settings.scheduler_heartbeat_seconds,
    )
    _register_interval_job(
        scheduler,
        job_id="event-relay",
        callable_=event_relay_worker.run_once,
        seconds=max(settings.event_relay_poll_seconds, 1.0),
    )
    _register_interval_job(
        scheduler,
        job_id="event-dispatch",
        callable_=broker_dispatch_worker.run_once,
        seconds=max(settings.event_broker_block_ms / 1000, 1.0),
    )
    _register_interval_job(
        scheduler,
        job_id="tradingagents-poll",
        callable_=tradingagents_worker.poll_once,
        seconds=tradingagents_worker.poll_interval,
    )
    _register_interval_job(
        scheduler,
        job_id="market-data-refresh",
        callable_=market_data_worker.run_once,
        seconds=market_data_worker.poll_interval,
    )
    _register_interval_job(
        scheduler,
        job_id="scanner-refresh",
        callable_=scanner_worker.run_once,
        seconds=scanner_worker.poll_interval,
    )
    _register_interval_job(
        scheduler,
        job_id="retention-maintenance",
        callable_=retention_worker.run_once,
        seconds=retention_worker.poll_interval_seconds,
    )
    _register_interval_job(
        scheduler,
        job_id="receipt-escalation",
        callable_=receipt_escalation_worker.run_once,
        seconds=300,
    )
    _register_interval_job(
        scheduler,
        job_id="push-dispatch",
        callable_=push_dispatch_worker.run_once,
        seconds=15,
    )
    _register_interval_job(
        scheduler,
        job_id="email-dispatch",
        callable_=email_dispatch_worker.run_once,
        seconds=15,
    )
    _register_interval_job(
        scheduler,
        job_id="backtest-refresh",
        callable_=backtest_worker.refresh_rankings,
        seconds=backtest_worker.poll_interval,
    )
    _register_interval_job(
        scheduler,
        job_id="cold-storage-archive",
        callable_=cold_storage_worker.archive_old_partitions,
        seconds=86400,
    )
    return scheduler


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    configure_tracing("scheduler")

    async def runner() -> None:
        scheduler = build_scheduler()
        scheduler.start()
        logger.info("Scheduler started")

        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()

        for shutdown_signal in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(shutdown_signal, stop_event.set)

        try:
            await stop_event.wait()
        finally:
            scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")

    await run_runtime_monitored(
        "scheduler",
        "scheduler",
        runner,
        metadata={"mode": "continuous"},
        heartbeat_interval_seconds=max(settings.scheduler_heartbeat_seconds / 2, 5),
        ttl_seconds=max(settings.scheduler_heartbeat_seconds * 3, 30),
        final_status="stopped",
    )


if __name__ == "__main__":
    asyncio.run(main())
