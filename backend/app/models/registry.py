import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, pg_enum, utcnow_column


class ReleaseStatus(enum.StrEnum):
    candidate = "candidate"
    active = "active"
    retired = "retired"


class ModelTarget(enum.StrEnum):
    pts = "pts"
    reb = "reb"
    ast = "ast"
    fg3m = "fg3m"
    stl = "stl"
    blk = "blk"
    min = "min"
    double_double = "double_double"


class Algorithm(enum.StrEnum):
    rolling_baseline = "rolling_baseline"
    ridge = "ridge"
    random_forest = "random_forest"
    xgboost = "xgboost"
    logistic = "logistic"
    xgboost_classifier = "xgboost_classifier"


class EvaluationSplit(enum.StrEnum):
    validation = "validation"
    test = "test"


class ModelRelease(Base):
    __tablename__ = "model_releases"
    __table_args__ = (
        Index(
            "uq_model_releases_single_active",
            "status",
            unique=True,
            postgresql_where="status = 'active'",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    version: Mapped[str] = mapped_column(String(32), unique=True)
    feature_schema_version: Mapped[str] = mapped_column(String(64))
    train_start: Mapped[date] = mapped_column(Date)
    train_end: Mapped[date] = mapped_column(Date)
    val_start: Mapped[date] = mapped_column(Date)
    val_end: Mapped[date] = mapped_column(Date)
    test_start: Mapped[date] = mapped_column(Date)
    test_end: Mapped[date] = mapped_column(Date)
    data_version: Mapped[int] = mapped_column(BigInteger)
    git_sha: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[ReleaseStatus] = mapped_column(pg_enum(ReleaseStatus, "release_status"))
    created_at: Mapped[datetime] = utcnow_column()
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (
        Index(
            "uq_model_versions_selected_target",
            "release_id",
            "target",
            unique=True,
            postgresql_where="is_selected",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    release_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("model_releases.id", ondelete="RESTRICT")
    )
    target: Mapped[ModelTarget] = mapped_column(pg_enum(ModelTarget, "model_target"))
    algorithm: Mapped[Algorithm] = mapped_column(pg_enum(Algorithm, "model_algorithm"))
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    hyperparameters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    features: Mapped[list[str]] = mapped_column(JSONB)
    interval_calibration: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    artifact_path: Mapped[str] = mapped_column(String(255))
    artifact_sha256: Mapped[str] = mapped_column(String(64))
    random_seed: Mapped[int] = mapped_column(Integer)


class ModelEvaluation(Base):
    __tablename__ = "model_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "model_version_id", "split", "season_id", postgresql_nulls_not_distinct=True
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("model_versions.id", ondelete="RESTRICT")
    )
    split: Mapped[EvaluationSplit] = mapped_column(pg_enum(EvaluationSplit, "evaluation_split"))
    season_id: Mapped[int | None] = mapped_column(ForeignKey("seasons.id", ondelete="RESTRICT"))
    n_observations: Mapped[int] = mapped_column(Integer)
    mae: Mapped[float | None] = mapped_column(Float)
    rmse: Mapped[float | None] = mapped_column(Float)
    r2: Mapped[float | None] = mapped_column(Float)
    interval_level: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    interval_coverage: Mapped[float | None] = mapped_column(Float)
    brier: Mapped[float | None] = mapped_column(Float)
    log_loss: Mapped[float | None] = mapped_column(Float)
    baseline_mae: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = utcnow_column()
