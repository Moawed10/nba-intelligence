"""live box scores

Revision ID: f3a9c1d7b250
Revises: d4f7a1c82e60
Create Date: 2026-11-17 01:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f3a9c1d7b250"
down_revision: str | None = "d4f7a1c82e60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "live_box_scores",
        sa.Column("game_id", sa.String(length=10), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period", sa.SmallInteger(), nullable=False),
        sa.Column("clock", sa.String(length=16), nullable=True),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ingestion_run_id", sa.BigInteger(), nullable=True),
        sa.Column("source_endpoint", sa.String(length=48), nullable=False),
        sa.Column(
            "first_ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("game_id"),
    )


def downgrade() -> None:
    op.drop_table("live_box_scores")
