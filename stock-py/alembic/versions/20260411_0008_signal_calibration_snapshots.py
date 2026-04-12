"""add signal calibration snapshots table

Revision ID: 20260411_0008
Revises: 20260409_0007
Create Date: 2026-04-11 12:15:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260411_0008"
down_revision = "20260409_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal_calibration_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("version", sa.String(length=120), nullable=False),
        sa.Column("source", sa.String(length=48), nullable=False, server_default=sa.text("'manual_review'")),
        sa.Column("snapshot", sa.Text(), nullable=False),
        sa.Column("derived_from", sa.String(length=160), nullable=True),
        sa.Column("sample_size", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("version", name="uq_signal_calibration_snapshots_version"),
    )
    op.create_index(
        "ix_signal_calibration_snapshots_source",
        "signal_calibration_snapshots",
        ["source"],
        unique=False,
    )
    op.create_index(
        "ix_signal_calibration_snapshots_derived_from",
        "signal_calibration_snapshots",
        ["derived_from"],
        unique=False,
    )
    op.create_index(
        "ix_signal_calibration_snapshots_is_active",
        "signal_calibration_snapshots",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        "ix_signal_calibration_snapshots_effective_at",
        "signal_calibration_snapshots",
        ["effective_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_signal_calibration_snapshots_effective_at",
        table_name="signal_calibration_snapshots",
    )
    op.drop_index(
        "ix_signal_calibration_snapshots_is_active",
        table_name="signal_calibration_snapshots",
    )
    op.drop_index(
        "ix_signal_calibration_snapshots_derived_from",
        table_name="signal_calibration_snapshots",
    )
    op.drop_index(
        "ix_signal_calibration_snapshots_source",
        table_name="signal_calibration_snapshots",
    )
    op.drop_table("signal_calibration_snapshots")