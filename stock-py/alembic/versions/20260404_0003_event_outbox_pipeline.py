"""add durable event outbox

Revision ID: 20260404_0003
Revises: 20260404_0002
Create Date: 2026-04-04 01:00:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260404_0003"
down_revision = "20260404_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_outbox",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("topic", sa.String(length=100), nullable=False),
        sa.Column("event_key", sa.String(length=255), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("headers", sa.JSON(), nullable=False),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("broker_message_id", sa.String(length=64), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_event_outbox_status_created_id",
        "event_outbox",
        ["status", "created_at", "id"],
    )
    op.create_index(
        "ix_event_outbox_topic_status_created_id",
        "event_outbox",
        ["topic", "status", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_event_outbox_topic_status_created_id", table_name="event_outbox")
    op.drop_index("ix_event_outbox_status_created_id", table_name="event_outbox")
    op.drop_table("event_outbox")
