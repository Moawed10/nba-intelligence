import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, pg_enum, utcnow_column


class RunStatus(enum.StrEnum):
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    abandoned = "abandoned"


class SyncEventType(enum.StrEnum):
    GAME_SCHEDULE_UPDATED = "GAME_SCHEDULE_UPDATED"
    GAME_STARTED = "GAME_STARTED"
    GAME_COMPLETED = "GAME_COMPLETED"
    GAME_STATS_FINALIZED = "GAME_STATS_FINALIZED"
    PLAYER_STATS_UPDATED = "PLAYER_STATS_UPDATED"
    HISTORICAL_DATA_CORRECTED = "HISTORICAL_DATA_CORRECTED"
    PREDICTION_STALE = "PREDICTION_STALE"
    INGESTION_FAILED = "INGESTION_FAILED"


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (Index("ix_ingestion_runs_job_status", "job", "status", "finished_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    job: Mapped[str] = mapped_column(String(48))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    status: Mapped[RunStatus] = mapped_column(pg_enum(RunStatus, "run_status"))
    started_at: Mapped[datetime] = utcnow_column()
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_count: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    rows_fetched: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rows_valid: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rows_inserted: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rows_updated: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error: Mapped[str | None] = mapped_column(Text)


class SyncSchedule(Base):
    __tablename__ = "sync_schedules"

    job: Mapped[str] = mapped_column(String(48), primary_key=True)
    interval_seconds: Mapped[int] = mapped_column(Integer)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class SyncEvent(Base):
    __tablename__ = "sync_events"
    __table_args__ = (
        Index("ix_sync_events_unprocessed", "id", postgresql_where="processed_at IS NULL"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    type: Mapped[SyncEventType] = mapped_column(pg_enum(SyncEventType, "sync_event_type"))
    dedupe_key: Mapped[str] = mapped_column(String(128), unique=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    ingestion_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingestion_runs.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = utcnow_column()
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SourceCorrection(Base):
    __tablename__ = "source_corrections"
    __table_args__ = (Index("ix_source_corrections_run", "ingestion_run_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ingestion_run_id: Mapped[int] = mapped_column(
        ForeignKey("ingestion_runs.id", ondelete="RESTRICT")
    )
    table_name: Mapped[str] = mapped_column(String(48))
    record_key: Mapped[dict[str, Any]] = mapped_column(JSONB)
    column_name: Mapped[str] = mapped_column(String(48))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    detected_at: Mapped[datetime] = utcnow_column()
