"""game prediction evaluations

Revision ID: b7e4c2a91d30
Revises: a7c31e5d9f02
Create Date: 2026-11-02 12:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e4c2a91d30"
down_revision: str | None = "a7c31e5d9f02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "game_prediction_evaluations",
        sa.Column("forecast_id", sa.Uuid(), nullable=False),
        sa.Column("home_actual", sa.SmallInteger(), nullable=False),
        sa.Column("away_actual", sa.SmallInteger(), nullable=False),
        sa.Column("home_abs_error", sa.Float(), nullable=False),
        sa.Column("away_abs_error", sa.Float(), nullable=False),
        sa.Column("home_within_interval", sa.Boolean(), nullable=False),
        sa.Column("away_within_interval", sa.Boolean(), nullable=False),
        sa.Column("winner_correct", sa.Boolean(), nullable=False),
        sa.Column("brier", sa.Float(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["forecast_id"],
            ["game_predictions.id"],
            name=op.f("fk_game_prediction_evaluations_forecast_id_game_predictions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("forecast_id", name=op.f("pk_game_prediction_evaluations")),
    )


def downgrade() -> None:
    op.drop_table("game_prediction_evaluations")
