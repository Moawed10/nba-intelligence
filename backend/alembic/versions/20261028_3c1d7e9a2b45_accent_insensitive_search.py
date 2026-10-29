"""accent-insensitive player search

Revision ID: 3c1d7e9a2b45
Revises: 8f0daf2fbf4a
Create Date: 2026-10-28 22:10:00
"""
from collections.abc import Sequence

from alembic import op

revision: str = "3c1d7e9a2b45"
down_revision: str | None = "8f0daf2fbf4a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute(
        """
        CREATE FUNCTION search_normalize(value text) RETURNS text
        LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
        RETURN lower(public.unaccent('public.unaccent'::regdictionary, value))
        """
    )
    op.drop_index("ix_players_full_name_trgm", table_name="players")
    op.execute(
        "CREATE INDEX ix_players_search_name_trgm ON players "
        "USING gin (search_normalize(full_name) gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_players_search_name_trgm")
    op.create_index(
        "ix_players_full_name_trgm",
        "players",
        ["full_name"],
        postgresql_using="gin",
        postgresql_ops={"full_name": "gin_trgm_ops"},
    )
    op.execute("DROP FUNCTION search_normalize(text)")
    op.execute("DROP EXTENSION IF EXISTS unaccent")
