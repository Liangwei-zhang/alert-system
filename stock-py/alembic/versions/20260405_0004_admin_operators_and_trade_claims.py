"""add admin operators and trade claim tracking

Revision ID: 20260405_0004
Revises: 20260404_0003
Create Date: 2026-04-05 03:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260405_0004"
down_revision = "20260404_0003"
branch_labels = None
depends_on = None

operator_role_enum = postgresql.ENUM(
    "viewer",
    "operator",
    "admin",
    name="admin_operator_role",
    create_type=False,
)


def upgrade() -> None:
    operator_role_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "admin_operators",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role", operator_role_enum, nullable=False, server_default=sa.text("'operator'")),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_action_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_admin_operators_role", "admin_operators", ["role"])

    op.add_column(
        "trade_log",
        sa.Column(
            "claimed_by_operator_id",
            sa.Integer(),
            sa.ForeignKey("admin_operators.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "trade_log",
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_trade_log_claimed_by_operator_id",
        "trade_log",
        ["claimed_by_operator_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_trade_log_claimed_by_operator_id", table_name="trade_log")
    op.drop_column("trade_log", "claimed_at")
    op.drop_column("trade_log", "claimed_by_operator_id")

    op.drop_index("ix_admin_operators_role", table_name="admin_operators")
    op.drop_table("admin_operators")
    operator_role_enum.drop(op.get_bind(), checkfirst=True)
