import sys

from locust import events

from tests.load.scenarios.auth_read import AuthReadUser
from tests.load.scenarios.dashboard_read import DashboardReadUser
from tests.load.scenarios.notification_read import NotificationReaderUser
from tests.load.scenarios.trade_action import TradeActionUser
from tests.load.scenarios.tradingagents_submit import TradingAgentsSubmitUser
from tests.load.validate_env import validate_or_raise


@events.test_start.add_listener
def validate_load_configuration(environment, **_: object) -> None:
    try:
        validate_or_raise(host=environment.host)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        environment.process_exit_code = 2
        if environment.runner is not None:
            environment.runner.quit()


__all__ = [
    "AuthReadUser",
    "DashboardReadUser",
    "NotificationReaderUser",
    "TradeActionUser",
    "TradingAgentsSubmitUser",
]
