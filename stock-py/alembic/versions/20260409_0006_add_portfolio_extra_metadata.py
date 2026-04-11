"""add portfolio extra metadata for staged exits

Revision ID: 20260409_0006
Revises: 20260409_0005
Create Date: 2026-04-09 18:40:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260409_0006"
down_revision = "20260409_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_portfolio", sa.Column("extra", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_portfolio", "extra")