from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


@lru_cache
def get_engine(url: str | None = None) -> Engine:
    settings = get_settings()
    return create_engine(
        url or settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        pool_timeout=settings.db_pool_timeout_seconds,
        connect_args={
            "options": "-c timezone=UTC",
            "connect_timeout": settings.db_connect_timeout_seconds,
        },
    )


@lru_cache
def api_engine(url: str | None = None) -> Engine:
    settings = get_settings()
    return create_engine(
        url or settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        pool_timeout=settings.db_pool_timeout_seconds,
        connect_args={
            "options": f"-c timezone=UTC -c statement_timeout={settings.api_statement_timeout_ms}",
            "connect_timeout": settings.db_connect_timeout_seconds,
        },
    )


def session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=engine or get_engine(), expire_on_commit=False)


@contextmanager
def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    session = session_factory(engine)()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


def current_data_version(session: Session) -> int | None:
    from app.models import IngestionRun, RunStatus

    return session.scalar(
        select(func.max(IngestionRun.id)).where(IngestionRun.status == RunStatus.succeeded)
    )
