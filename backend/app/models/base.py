import enum
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, MetaData, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def pg_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    return Enum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])


def utcnow_column(**kwargs: Any) -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), **kwargs)


class Provenance:
    """Source provenance carried by every ingested row."""

    @declared_attr
    def ingestion_run_id(cls) -> Mapped[int | None]:
        return mapped_column(BigInteger, ForeignKey("ingestion_runs.id", ondelete="RESTRICT"))

    source_endpoint: Mapped[str] = mapped_column(String(48))
    first_ingested_at: Mapped[datetime] = utcnow_column()
    updated_at: Mapped[datetime] = utcnow_column()


PROVENANCE_COLUMNS = ("ingestion_run_id", "source_endpoint", "first_ingested_at", "updated_at")
