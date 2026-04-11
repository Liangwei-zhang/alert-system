from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable

if TYPE_CHECKING:
    from infra.events.bus import EventBus


EventHandler = Callable[[str, dict[str, Any]], Awaitable[Any]]


def register_default_subscribers(bus: "EventBus") -> None:
    from apps.workers.analytics_sink.worker import AnalyticsSinkWorker
    from apps.workers.notification_orchestrator.worker import NotificationOrchestratorWorker

    notification_worker = NotificationOrchestratorWorker()
    analytics_worker = AnalyticsSinkWorker()

    for topic in ("signal.generated", "notification.batch.requested", "tradingagents.terminal"):
        bus.subscribe(
            topic, notification_worker.process_event, subscriber_id="notification-orchestrator"
        )

    for topic in (
        "signal.generated",
        "notification.batch.requested",
        "notification.push.batch.requested",
        "scanner.decision.recorded",
        "strategy.rankings.refreshed",
        "notification.requested",
        "notification.delivered",
        "notification.acknowledged",
        "trade.action.recorded",
        "account.subscription.started",
        "watchlist.changed",
        "portfolio.changed",
        "tradingagents.requested",
        "tradingagents.terminal",
    ):
        bus.subscribe(topic, analytics_worker.handle_event, subscriber_id="analytics-sink")
