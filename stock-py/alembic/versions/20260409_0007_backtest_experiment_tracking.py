"""add experiment tracking metadata to backtest runs

Revision ID: 20260409_0007
Revises: 20260409_0006
Create Date: 2026-04-09 21:30:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260409_0007"
down_revision = "20260409_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("backtest_runs", sa.Column("experiment_name", sa.String(length=120), nullable=True))
    op.add_column("backtest_runs", sa.Column("run_key", sa.String(length=160), nullable=True))
    op.add_column("backtest_runs", sa.Column("config", sa.Text(), nullable=True))
    op.add_column("backtest_runs", sa.Column("artifacts", sa.Text(), nullable=True))
    op.add_column("backtest_runs", sa.Column("code_version", sa.String(length=128), nullable=True))
    op.add_column(
        "backtest_runs",
        sa.Column("dataset_fingerprint", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_backtest_runs_experiment_name",
        "backtest_runs",
        ["experiment_name"],
        unique=False,
    )
    op.create_index("ix_backtest_runs_run_key", "backtest_runs", ["run_key"], unique=False)
    op.create_index(
        "ix_backtest_runs_dataset_fingerprint",
        "backtest_runs",
        ["dataset_fingerprint"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_backtest_runs_dataset_fingerprint", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_run_key", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_experiment_name", table_name="backtest_runs")
    op.drop_column("backtest_runs", "dataset_fingerprint")
    op.drop_column("backtest_runs", "code_version")
    op.drop_column("backtest_runs", "artifacts")
    op.drop_column("backtest_runs", "config")
    op.drop_column("backtest_runs", "run_key")
    op.drop_column("backtest_runs", "experiment_name")