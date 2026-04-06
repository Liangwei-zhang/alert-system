from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from infra.core.errors import AppError


class ReceiptRepositoryProtocol(Protocol):
    async def list_overdue_receipts(self, limit: int = 100) -> list[Any]: ...

    async def get_by_id(self, receipt_id: str): ...

    async def mark_manual_follow_up_pending(
        self,
        receipt_id: str,
        escalation_level: int,
    ): ...

    async def claim_manual_follow_up(self, receipt_id: str): ...

    async def resolve_follow_up(self, receipt_id: str): ...


@dataclass(slots=True)
class ReceiptEscalationSummary:
    scanned: int
    escalated: int
    skipped: int


class ReceiptEscalationService:
    def __init__(self, receipt_repository: ReceiptRepositoryProtocol) -> None:
        self.receipt_repository = receipt_repository

    async def scan_and_escalate(self, limit: int = 100) -> ReceiptEscalationSummary:
        receipts = await self.receipt_repository.list_overdue_receipts(limit=limit)
        escalated = 0
        skipped = 0

        for receipt in receipts:
            status = str(getattr(receipt, "manual_follow_up_status", "none") or "none")
            if status in {"claimed", "resolved"}:
                skipped += 1
                continue

            next_level = int(getattr(receipt, "escalation_level", 0) or 0) + 1
            await self.receipt_repository.mark_manual_follow_up_pending(
                str(receipt.id),
                next_level,
            )
            escalated += 1

        return ReceiptEscalationSummary(
            scanned=len(receipts),
            escalated=escalated,
            skipped=skipped,
        )

    async def claim_manual_follow_up(self, receipt_id: str):
        receipt = await self.receipt_repository.get_by_id(receipt_id)
        if receipt is None:
            raise AppError(
                "receipt_not_found",
                "Receipt not found",
                status_code=404,
            )
        if str(getattr(receipt, "manual_follow_up_status", "none") or "none") == "resolved":
            raise AppError(
                "receipt_follow_up_resolved",
                "Receipt follow-up is already resolved",
                status_code=409,
            )
        return await self.receipt_repository.claim_manual_follow_up(receipt_id)

    async def resolve_follow_up(self, receipt_id: str):
        receipt = await self.receipt_repository.get_by_id(receipt_id)
        if receipt is None:
            raise AppError(
                "receipt_not_found",
                "Receipt not found",
                status_code=404,
            )
        return await self.receipt_repository.resolve_follow_up(receipt_id)
