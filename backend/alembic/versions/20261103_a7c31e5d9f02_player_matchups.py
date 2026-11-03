"""who guarded whom, per game

Revision ID: a7c31e5d9f02
Revises: 4b1b118f51b1
Create Date: 2026-11-03 10:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7c31e5d9f02"
down_revision: str | None = "4b1b118f51b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "player_matchups",
        sa.Column("game_id", sa.String(length=10), nullable=False),
        sa.Column("off_player_id", sa.Integer(), nullable=False),
        sa.Column("def_player_id", sa.Integer(), nullable=False),
        sa.Column("off_team_id", sa.Integer(), nullable=False),
        sa.Column("def_team_id", sa.Integer(), nullable=False),
        sa.Column("seconds", sa.Numeric(precision=7, scale=1), nullable=False),
        sa.Column("partial_possessions", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("pts", sa.SmallInteger(), nullable=False),
        sa.Column("ast", sa.SmallInteger(), nullable=False),
        sa.Column("tov", sa.SmallInteger(), nullable=False),
        sa.Column("fgm", sa.SmallInteger(), nullable=False),
        sa.Column("fga", sa.SmallInteger(), nullable=False),
        sa.Column("fg3m", sa.SmallInteger(), nullable=False),
        sa.Column("fg3a", sa.SmallInteger(), nullable=False),
        sa.Column("ingestion_run_id", sa.BigInteger(), nullable=True),
        sa.Column("source_endpoint", sa.String(length=48), nullable=False),
        sa.Column(
            "first_ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("partial_possessions > 0", name="possessions_positive"),
        sa.CheckConstraint("seconds >= 0", name="seconds_nonnegative"),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["off_player_id"], ["players.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["def_player_id"], ["players.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["off_team_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["def_team_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("game_id", "off_player_id", "def_player_id"),
    )
    op.create_index("ix_matchups_offense", "player_matchups", ["off_player_id", "game_id"])
    op.create_index("ix_matchups_defense", "player_matchups", ["def_player_id", "game_id"])
    op.create_index("ix_matchups_def_team", "player_matchups", ["def_team_id", "game_id"])


def downgrade() -> None:
    op.drop_table("player_matchups")
