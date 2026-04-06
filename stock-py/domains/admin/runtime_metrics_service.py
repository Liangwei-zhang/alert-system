from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from domains.notifications.repository import MessageOutboxRepository, ReceiptRepository
from domains.trades.repository import TradeRepository
from infra.events.outbox import EventOutboxRepository


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class RuntimeOperationalMetricPoint:
    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)


class RuntimeOperationalMetricsService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        receipt_repository: ReceiptRepository | None = None,
        outbox_repository: MessageOutboxRepository | None = None,
        event_outbox_repository: EventOutboxRepository | None = None,
        trade_repository: TradeRepository | None = None,
        outbox_channels: tuple[str, ...] = ("email", "push"),
        claim_latency_window_days: int = 7,
        claim_latency_sample_limit: int = 1000,
    ) -> None:
        self.session = session
        self.receipt_repository = receipt_repository or ReceiptRepository(session)
        self.outbox_repository = outbox_repository or MessageOutboxRepository(session)
        self.event_outbox_repository = event_outbox_repository or EventOutboxRepository(session)
        self.trade_repository = trade_repository or TradeRepository(session)
        self.outbox_channels = tuple(
            channel.strip().lower() for channel in outbox_channels if channel.strip()
        )
        self.claim_latency_window_days = max(int(claim_latency_window_days), 1)
        self.claim_latency_sample_limit = max(int(claim_latency_sample_limit), 1)

    async def collect_metric_points(self) -> list[RuntimeOperationalMetricPoint]:
        queries: list[tuple[str | tuple[str, str, str], object]] = [
            (
                ("notification_outbox_messages_total", "status", "pending"),
                self.outbox_repository.count_admin_messages(status="pending"),
            ),
            (
                ("notification_outbox_messages_total", "status", "processing"),
                self.outbox_repository.count_admin_messages(status="processing"),
            ),
            (
                ("notification_outbox_messages_total", "status", "failed"),
                self.outbox_repository.count_admin_messages(status="failed"),
            ),
            (
                ("notification_receipts_total", "state", "overdue"),
                self.receipt_repository.count_admin_receipts(overdue_only=True, ack_required=True),
            ),
            (
                ("notification_manual_follow_up_total", "status", "pending"),
                self.receipt_repository.count_admin_receipts(follow_up_status="pending"),
            ),
            (
                ("notification_manual_follow_up_total", "status", "claimed"),
                self.receipt_repository.count_admin_receipts(follow_up_status="claimed"),
            ),
            (
                ("notification_receipt_deliveries_total", "status", "delivered"),
                self.receipt_repository.count_admin_receipts(delivery_status="delivered"),
            ),
            (
                ("notification_receipt_deliveries_total", "status", "failed"),
                self.receipt_repository.count_admin_receipts(delivery_status="failed"),
            ),
            (
                ("event_outbox_records_total", "status", "pending"),
                self.event_outbox_repository.count_runtime_records(status="pending"),
            ),
            (
                ("event_outbox_records_total", "status", "published"),
                self.event_outbox_repository.count_runtime_records(status="published"),
            ),
            (
                ("event_outbox_records_total", "status", "dead_letter"),
                self.event_outbox_repository.count_runtime_records(status="dead_letter"),
            ),
            (
                "event_outbox_retried_total",
                self.event_outbox_repository.count_runtime_records(
                    status="pending",
                    retried_only=True,
                ),
            ),
            (
                ("trade_tasks_total", "state", "claimable"),
                self.trade_repository.count_claimable_trades(),
            ),
            (
                ("trade_tasks_total", "state", "expirable"),
                self.trade_repository.count_expirable_trades(),
            ),
            (
                "trade_claim_latency_stats",
                self.trade_repository.get_claim_latency_stats(
                    since=utcnow() - timedelta(days=self.claim_latency_window_days),
                    limit=self.claim_latency_sample_limit,
                ),
            ),
        ]

        for channel in self.outbox_channels:
            for status in ("pending", "processing", "failed"):
                queries.append(
                    (
                        (
                            "notification_outbox_channel_messages_total",
                            channel,
                            status,
                        ),
                        self.outbox_repository.count_admin_messages(channel=channel, status=status),
                    )
                )

        results = await asyncio.gather(*(query for _key, query in queries))
        metrics: list[RuntimeOperationalMetricPoint] = []
        for (key, _query), result in zip(queries, results, strict=False):
            if key == "trade_claim_latency_stats":
                stats = dict(result or {})
                sample_count = float(stats.get("count") or 0)
                metrics.append(
                    RuntimeOperationalMetricPoint(
                        name="trade_claim_latency_samples_total",
                        value=sample_count,
                    )
                )
                if sample_count > 0:
                    metrics.append(
                        RuntimeOperationalMetricPoint(
                            name="trade_claim_latency_seconds_avg",
                            value=round(float(stats.get("avg_seconds") or 0.0), 2),
                        )
                    )
                    metrics.append(
                        RuntimeOperationalMetricPoint(
                            name="trade_claim_latency_seconds_max",
                            value=round(float(stats.get("max_seconds") or 0.0), 2),
                        )
                    )
                continue

            if key == "event_outbox_retried_total":
                metrics.append(
                    RuntimeOperationalMetricPoint(
                        name="event_outbox_retried_total",
                        value=float(result or 0),
                    )
                )
                continue

            if not isinstance(key, tuple):
                continue

            if key[0] == "notification_outbox_channel_messages_total":
                metrics.append(
                    RuntimeOperationalMetricPoint(
                        name=key[0],
                        value=float(result or 0),
                        labels={"channel": key[1], "status": key[2]},
                    )
                )
                continue

            metrics.append(
                RuntimeOperationalMetricPoint(
                    name=key[0],
                    value=float(result or 0),
                    labels={key[1]: key[2]},
                )
            )

        return metrics
