"""jersey numbers and the current injury report

Revision ID: c2e4a9d71b36
Revises: a7c31e5d9f02
Create Date: 2026-11-03 18:30:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c2e4a9d71b36"
down_revision: str | None = "a7c31e5d9f02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("players", sa.Column("jersey_number", sa.String(length=8), nullable=True))
    op.create_table(
        "player_injuries",
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("injury", sa.String(length=64), nullable=True),
        sa.Column("detail", sa.String(length=64), nullable=True),
        sa.Column("side", sa.String(length=24), nullable=True),
        sa.Column("return_date", sa.Date(), nullable=True),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingestion_run_id", sa.BigInteger(), nullable=True),
        sa.Column("source_endpoint", sa.String(length=48), nullable=False),
        sa.Column("first_ingested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], name=op.f("fk_player_injuries_player_id_players"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"], name=op.f("fk_player_injuries_ingestion_run_id_ingestion_runs"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("player_id", name=op.f("pk_player_injuries")),
    )


def downgrade() -> None:
    op.drop_table("player_injuries")
    op.drop_column("players", "jersey_number")
