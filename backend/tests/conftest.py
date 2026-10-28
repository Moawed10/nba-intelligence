import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, make_url, text

from app.models import Base

BACKEND = Path(__file__).resolve().parents[1]
TEST_URL = os.environ.get("NBA_TEST_DATABASE_URL", "postgresql+psycopg:///nba_intelligence_test")


def _recreate_database(url: str) -> None:
    parsed = make_url(url)
    admin = parsed.set(database="postgres").render_as_string(hide_password=False)
    admin = admin.replace("postgresql+psycopg", "postgresql")
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{parsed.database}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{parsed.database}"')


def alembic_config(url: str) -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


@pytest.fixture(scope="session")
def migrated_url() -> str:
    try:
        _recreate_database(TEST_URL)
    except psycopg.OperationalError as exc:
        pytest.skip(f"PostgreSQL test database unavailable: {exc}")
    command.upgrade(alembic_config(TEST_URL), "head")
    return TEST_URL


@pytest.fixture(scope="session")
def session_engine(migrated_url: str) -> Iterator[Engine]:
    engine = create_engine(migrated_url)
    yield engine
    engine.dispose()


@pytest.fixture
def engine(session_engine: Engine) -> Engine:
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with session_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    return session_engine
