import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.models import Base
from tests.conftest import alembic_config

pytestmark = pytest.mark.integration


def test_models_match_migrations(migrated_url):
    engine = create_engine(migrated_url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diff == []


def test_downgrade_and_upgrade_round_trip(migrated_url):
    cfg = alembic_config(migrated_url)
    command.downgrade(cfg, "base")
    engine = create_engine(migrated_url)
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    command.upgrade(cfg, "head")
    assert set(inspect(engine).get_table_names()) - {"alembic_version"} == set(Base.metadata.tables)
    engine.dispose()
