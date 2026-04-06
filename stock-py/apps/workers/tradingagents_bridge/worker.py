"""
Polling worker for TradingAgents job status.
"""

import asyncio
import logging

from domains.tradingagents.gateway import TradingAgentsApiError, TradingAgentsGateway
from domains.tradingagents.projection_mapper import TradingAgentsProjectionMapper
from domains.tradingagents.repository import TradingAgentsRepository
from infra.db.session import get_session_factory
from infra.observability.runtime_monitoring import run_runtime_monitored

logger = logging.getLogger(__name__)


class TradingAgentsPollingWorker:
    """
    Worker that polls TradingAgents for job status updates.

    Runs continuously and polls pending/submitted/running jobs.
    """

    def __init__(
        self,
        poll_interval_seconds: int = 30,
        batch_size: int = 50,
        delayed_threshold_minutes: int = 30,
    ):
        self.poll_interval = poll_interval_seconds
        self.batch_size = batch_size
        self.delayed_threshold = delayed_threshold_minutes
        self.gateway = TradingAgentsGateway()
        self.mapper = TradingAgentsProjectionMapper()
        self._running = False

    async def run_forever(
        self,
        initial_delay: float = 5.0,
    ):
        """
        Run the worker continuously.

        Args:
            initial_delay: Initial delay before first poll
        """
        logger.info("Starting TradingAgents polling worker")

        # Initial delay
        await asyncio.sleep(initial_delay)

        self._running = True

        while self._running:
            try:
                await self.poll_once()
            except Exception as e:
                logger.error(f"Error in poll cycle: {e}", exc_info=True)

            # Wait before next cycle
            await asyncio.sleep(self.poll_interval)

        logger.info("TradingAgents polling worker stopped")

    async def poll_once(self) -> dict:
        """
        Perform one polling cycle.

        Returns:
            Dict with statistics
        """
        stats = {
            "checked": 0,
            "completed": 0,
            "failed": 0,
            "still_running": 0,
            "errors": 0,
        }

        session_factory = get_session_factory()

        async with session_factory() as session:
            repository = TradingAgentsRepository(session)

            # Get pending jobs
            pending_records = await repository.list_pending(
                limit=self.batch_size,
                older_than_minutes=1,  # Jobs older than 1 minute
            )

            stats["checked"] = len(pending_records)

            for record in pending_records:
                if not record.job_id:
                    continue

                try:
                    result = await self.process_record(repository, record)

                    if result == "completed":
                        stats["completed"] += 1
                    elif result == "failed":
                        stats["failed"] += 1
                    else:
                        stats["still_running"] += 1

                except Exception as e:
                    logger.error(f"Error processing record {record.request_id}: {e}", exc_info=True)
                    stats["errors"] += 1

            # Check for delayed jobs
            delayed_records = await repository.list_delayed(
                delayed_threshold_minutes=self.delayed_threshold
            )

            for record in delayed_records:
                try:
                    await repository.mark_delayed(record.request_id)
                    logger.info(f"Marked {record.request_id} as delayed")
                except Exception as e:
                    logger.error(f"Error marking delayed: {e}")

        if stats["checked"] > 0:
            logger.info(
                f"Poll cycle: checked={stats['checked']}, "
                f"completed={stats['completed']}, failed={stats['failed']}, "
                f"running={stats['still_running']}, errors={stats['errors']}"
            )

        return stats

    async def process_record(
        self,
        repository: TradingAgentsRepository,
        record,
    ) -> str:
        """
        Process a single record.

        Returns:
            Status: "completed", "failed", "running", "error"
        """
        # Increment poll count
        await repository.increment_poll_count(record.request_id)

        try:
            # Poll gateway
            poll_result = await self.gateway.get_stock_result(record.job_id)

            if not poll_result:
                return "running"

            status = poll_result.get("status", "unknown")

            # Map to projection
            projection = self.mapper.from_poll_response(
                request_id=record.request_id,
                job_id=record.job_id,
                poll_data=poll_result,
            )

            # Update record
            await repository.update_projection(
                request_id=record.request_id,
                job_id=record.job_id,
                tradingagents_status=projection.tradingagents_status,
                final_action=projection.final_action,
                decision_summary=projection.decision_summary,
                result_payload=projection.result_payload,
            )

            # Handle terminal states
            if status == "completed":
                await repository.mark_completed(
                    request_id=record.request_id,
                    final_action=projection.final_action or "unknown",
                    decision_summary=projection.decision_summary,
                    result_payload=projection.result_payload,
                )
                logger.info(f"Job {record.request_id} completed: {projection.final_action}")
                return "completed"

            elif status == "failed":
                await repository.mark_failed(
                    request_id=record.request_id,
                    error_message=projection.decision_summary or "Job failed",
                )
                logger.warning(f"Job {record.request_id} failed")
                return "failed"

            elif status == "timeout":
                await repository.mark_failed(
                    request_id=record.request_id,
                    error_message="Job timed out",
                )
                logger.warning(f"Job {record.request_id} timed out")
                return "failed"

            return "running"

        except TradingAgentsApiError as e:
            logger.error(f"API error polling {record.request_id}: {e}")
            return "error"

    def stop(self):
        """Stop the worker."""
        logger.info("Stopping TradingAgents polling worker")
        self._running = False


async def main():
    """Main entry point for the worker."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    worker = TradingAgentsPollingWorker(
        poll_interval_seconds=30,
        batch_size=50,
        delayed_threshold_minutes=30,
    )

    async def runner() -> None:
        await worker.run_forever()

    try:
        await run_runtime_monitored(
            "tradingagents-bridge",
            "worker",
            runner,
            metadata={"mode": "continuous"},
            heartbeat_interval_seconds=10,
            ttl_seconds=30,
            final_status="stopped",
        )
    except KeyboardInterrupt:
        worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
