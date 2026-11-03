"""game attendance

Revision ID: e81f6b0c3a47
Revises: c2e4a9d71b36
Create Date: 2026-11-03 19:30:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e81f6b0c3a47"
down_revision: str | None = "c2e4a9d71b36"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("games", sa.Column("attendance", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("games", "attendance")
