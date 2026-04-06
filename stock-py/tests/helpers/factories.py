from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserFactory:
    @staticmethod
    def create_user(user_id: int = 1, email: str = "user@example.com") -> dict:
        return {
            "id": user_id,
            "email": email,
            "created_at": _utcnow(),
            "last_login_at": _utcnow(),
        }

    @staticmethod
    def create_session(user_id: int = 1, refresh_token: str = "refresh-token") -> dict:
        return {
            "id": str(uuid4()),
            "user_id": user_id,
            "refresh_token": refresh_token,
            "created_at": _utcnow(),
        }


class WatchlistFactory:
    @staticmethod
    def create_watchlist_item(user_id: int = 1, symbol: str = "AAPL") -> dict:
        return {
            "id": str(uuid4()),
            "user_id": user_id,
            "symbol": symbol,
            "created_at": _utcnow(),
        }


class PortfolioFactory:
    @staticmethod
    def create_portfolio_position(user_id: int = 1, symbol: str = "AAPL") -> dict:
        return {
            "id": str(uuid4()),
            "user_id": user_id,
            "symbol": symbol,
            "shares": 10,
            "avg_cost": 100.0,
            "created_at": _utcnow(),
        }


class NotificationFactory:
    @staticmethod
    def create_notification_with_receipt(
        user_id: int = 1, notification_type: str = "signal.generated"
    ) -> dict:
        return {
            "notification": {
                "id": str(uuid4()),
                "user_id": user_id,
                "type": notification_type,
                "title": "Notification title",
                "body": "Notification body",
                "created_at": _utcnow(),
            },
            "receipt": {
                "id": str(uuid4()),
                "user_id": user_id,
                "ack_required": False,
                "created_at": _utcnow(),
            },
        }
