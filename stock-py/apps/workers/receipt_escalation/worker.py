from __future__ import annotations

import asyncio
import logging

from infra.observability.runtime_monitoring import run_runtime_monitored

logger = logging.getLogger(__name__)


class ReceiptEscalationWorker:
    def __init__(self, batch_size: int = 100) -> None:
        self.batch_size = batch_size

    async def run_once(self) -> dict[str, int]:
        from domains.notifications.receipt_service import ReceiptEscalationService
        from domains.notifications.repository import ReceiptRepository
        from infra.db.session import get_session_factory

        session_factory = get_session_factory()
        async with session_factory() as session:
            service = ReceiptEscalationService(ReceiptRepository(session))
            summary = await service.scan_and_escalate(limit=self.batch_size)
            await session.commit()
        return {
            "scanned": summary.scanned,
            "escalated": summary.escalated,
            "skipped": summary.skipped,
        }


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    result = await run_runtime_monitored(
        "receipt-escalation",
        "worker",
        ReceiptEscalationWorker().run_once,
        metadata={"mode": "batch"},
        final_status="completed",
    )
    logger.info("Receipt escalation batch finished: %s", result)


if __name__ == "__main__":
    asyncio.run(main())
