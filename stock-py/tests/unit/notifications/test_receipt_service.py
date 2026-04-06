import asyncio
import unittest
from types import SimpleNamespace

from domains.notifications.receipt_service import ReceiptEscalationService
from infra.core.errors import AppError


class FakeReceiptRepository:
    def __init__(self, receipts):
        self.receipts = {receipt.id: receipt for receipt in receipts}

    async def list_overdue_receipts(self, limit: int = 100):
        return list(self.receipts.values())[:limit]

    async def get_by_id(self, receipt_id: str):
        return self.receipts.get(receipt_id)

    async def mark_manual_follow_up_pending(self, receipt_id: str, escalation_level: int):
        receipt = self.receipts[receipt_id]
        receipt.manual_follow_up_status = "pending"
        receipt.escalation_level = escalation_level
        return receipt

    async def claim_manual_follow_up(self, receipt_id: str):
        receipt = self.receipts[receipt_id]
        receipt.manual_follow_up_status = "claimed"
        return receipt

    async def resolve_follow_up(self, receipt_id: str):
        receipt = self.receipts[receipt_id]
        receipt.manual_follow_up_status = "resolved"
        return receipt


class ReceiptEscalationServiceTest(unittest.TestCase):
    def test_scan_and_escalate_updates_unresolved_receipts(self) -> None:
        repository = FakeReceiptRepository(
            [
                SimpleNamespace(id="r1", escalation_level=0, manual_follow_up_status="none"),
                SimpleNamespace(id="r2", escalation_level=2, manual_follow_up_status="claimed"),
                SimpleNamespace(id="r3", escalation_level=1, manual_follow_up_status="pending"),
            ]
        )
        service = ReceiptEscalationService(repository)

        summary = asyncio.run(service.scan_and_escalate())

        self.assertEqual(summary.scanned, 3)
        self.assertEqual(summary.escalated, 2)
        self.assertEqual(summary.skipped, 1)
        self.assertEqual(repository.receipts["r1"].escalation_level, 1)
        self.assertEqual(repository.receipts["r3"].escalation_level, 2)

    def test_claim_manual_follow_up_raises_for_missing_receipt(self) -> None:
        service = ReceiptEscalationService(FakeReceiptRepository([]))

        with self.assertRaises(AppError):
            asyncio.run(service.claim_manual_follow_up("missing"))

    def test_resolve_follow_up_marks_receipt_resolved(self) -> None:
        repository = FakeReceiptRepository(
            [SimpleNamespace(id="r1", escalation_level=1, manual_follow_up_status="claimed")]
        )
        service = ReceiptEscalationService(repository)

        receipt = asyncio.run(service.resolve_follow_up("r1"))

        self.assertEqual(receipt.manual_follow_up_status, "resolved")


if __name__ == "__main__":
    unittest.main()
