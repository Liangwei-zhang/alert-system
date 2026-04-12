"""add effective_from to calibration snapshots

Revision ID: 20260412_0009
Revises: 20260411_0008
Create Date: 2026-04-12 09:30:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260412_0009"
down_revision = "20260411_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "signal_calibration_snapshots",
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE signal_calibration_snapshots
            SET effective_from = effective_at
            WHERE effective_from IS NULL AND effective_at IS NOT NULL
            """
        )
    )
    op.create_index(
        "ix_signal_calibration_snapshots_effective_from",
        "signal_calibration_snapshots",
        ["effective_from"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_signal_calibration_snapshots_effective_from",
        table_name="signal_calibration_snapshots",
    )
    op.drop_column("signal_calibration_snapshots", "effective_from")