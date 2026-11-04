"""fan posts

Revision ID: d4f7a1c82e60
Revises: b7e4c2a91d30
Create Date: 2026-11-04 01:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4f7a1c82e60"
down_revision: str | None = "b7e4c2a91d30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fan_posts",
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("uri", sa.String(length=512), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("author_handle", sa.String(length=253), nullable=False),
        sa.Column("author_name", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("likes", sa.Integer(), nullable=False),
        sa.Column("reposts", sa.Integer(), nullable=False),
        sa.Column("replies", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
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
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("team_id", "uri"),
    )


def downgrade() -> None:
    op.drop_table("fan_posts")
