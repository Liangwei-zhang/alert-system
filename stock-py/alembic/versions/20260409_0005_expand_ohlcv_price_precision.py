"""expand ohlcv price precision for adjusted archive imports

Revision ID: 20260409_0005
Revises: 20260405_0004
Create Date: 2026-04-09 14:15:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260409_0005"
down_revision = "20260405_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column_name in ("open", "high", "low", "close"):
        op.alter_column(
            "ohlcv",
            column_name,
            existing_type=sa.Numeric(15, 6),
            type_=sa.Numeric(24, 6),
            existing_nullable=False,
        )


def downgrade() -> None:
    for column_name in ("close", "low", "high", "open"):
        op.alter_column(
            "ohlcv",
            column_name,
            existing_type=sa.Numeric(24, 6),
            type_=sa.Numeric(15, 6),
            existing_nullable=False,
        )