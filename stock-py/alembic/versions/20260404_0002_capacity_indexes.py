"""add capacity-oriented indexes

Revision ID: 20260404_0002
Revises: 20260404_0001
Create Date: 2026-04-04 00:30:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260404_0002"
down_revision = "20260404_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_email_codes_email_code_valid",
        "email_codes",
        ["email", "code", "used_at", "expires_at"],
    )
    op.create_index(
        "ix_user_watchlist_notify_symbol",
        "user_watchlist",
        ["notify", "symbol"],
    )
    op.create_index(
        "ix_user_watchlist_user_created",
        "user_watchlist",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_user_portfolio_notify_symbol",
        "user_portfolio",
        ["notify", "symbol"],
    )
    op.create_index(
        "ix_user_portfolio_user_total_capital",
        "user_portfolio",
        ["user_id", "total_capital"],
    )
    op.create_index(
        "ix_notifications_user_created_id",
        "notifications",
        ["user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_notifications_user_is_read_created_id",
        "notifications",
        ["user_id", "is_read", "created_at", "id"],
    )
    op.create_index(
        "ix_push_subscriptions_user_active_seen_created",
        "push_subscriptions",
        ["user_id", "is_active", "last_seen_at", "created_at"],
    )
    op.create_index(
        "ix_message_outbox_channel_status_created_id",
        "message_outbox",
        ["channel", "status", "created_at", "id"],
    )
    op.create_index(
        "ix_message_receipts_notification_user_created",
        "message_receipts",
        ["notification_id", "user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_message_receipts_notification_user_created", table_name="message_receipts")
    op.drop_index("ix_message_outbox_channel_status_created_id", table_name="message_outbox")
    op.drop_index(
        "ix_push_subscriptions_user_active_seen_created",
        table_name="push_subscriptions",
    )
    op.drop_index(
        "ix_notifications_user_is_read_created_id",
        table_name="notifications",
    )
    op.drop_index("ix_notifications_user_created_id", table_name="notifications")
    op.drop_index("ix_user_portfolio_user_total_capital", table_name="user_portfolio")
    op.drop_index("ix_user_portfolio_notify_symbol", table_name="user_portfolio")
    op.drop_index("ix_user_watchlist_user_created", table_name="user_watchlist")
    op.drop_index("ix_user_watchlist_notify_symbol", table_name="user_watchlist")
    op.drop_index("ix_email_codes_email_code_valid", table_name="email_codes")
