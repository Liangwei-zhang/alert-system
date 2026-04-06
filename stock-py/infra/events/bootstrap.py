from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable

if TYPE_CHECKING:
    from infra.events.bus import EventBus


EventHandler = Callable[[str, dict[str, Any]], Awaitable[Any]]


def register_default_subscribers(bus: "EventBus") -> None:
    from apps.workers.analytics_sink.worker import AnalyticsSinkWorker
    from apps.workers.email_dispatch.worker import EmailDispatchWorker
    from apps.workers.notification_orchestrator.worker import NotificationOrchestratorWorker
    from apps.workers.push_dispatch.worker import PushDispatchWorker

    notification_worker = NotificationOrchestratorWorker()
    analytics_worker = AnalyticsSinkWorker()
    push_worker = PushDispatchWorker()
    email_worker = EmailDispatchWorker()

    for topic in ("signal.generated", "tradingagents.terminal"):
        bus.subscribe(
            topic, notification_worker.process_event, subscriber_id="notification-orchestrator"
        )

    for topic in (
        "signal.generated",
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

    bus.subscribe(
        "notification.requested", push_worker.process_event, subscriber_id="push-dispatch"
    )
    bus.subscribe(
        "notification.requested", email_worker.process_event, subscriber_id="email-dispatch"
    )
