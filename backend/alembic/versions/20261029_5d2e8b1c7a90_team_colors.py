"""team brand colors

Revision ID: 5d2e8b1c7a90
Revises: 3c1d7e9a2b45
Create Date: 2026-10-29 03:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.ingestion.transforms import TEAM_COLORS

revision: str = "5d2e8b1c7a90"
down_revision: str | None = "3c1d7e9a2b45"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPDATE = sa.text(
    "UPDATE teams SET primary_color = :primary, secondary_color = :secondary "
    "WHERE abbreviation = :abbreviation"
)


def upgrade() -> None:
    for abbreviation, (primary, secondary) in TEAM_COLORS.items():
        op.get_bind().execute(
            UPDATE, {"abbreviation": abbreviation, "primary": primary, "secondary": secondary}
        )


def downgrade() -> None:
    op.execute("UPDATE teams SET primary_color = NULL, secondary_color = NULL")
