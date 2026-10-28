import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, pg_enum, utcnow_column


class PredictionKind(enum.StrEnum):
    pregame = "pregame"
    backtest = "backtest"


class PredictionStatus(enum.StrEnum):
    ok = "ok"
    insufficient_data = "insufficient_data"
    model_unavailable = "model_unavailable"


class PredictedStat(enum.StrEnum):
    pts = "pts"
    reb = "reb"
    ast = "ast"
    fg3m = "fg3m"
    stl = "stl"
    blk = "blk"
    min = "min"


class EvaluatedStat(enum.StrEnum):
    pts = "pts"
    reb = "reb"
    ast = "ast"
    fg3m = "fg3m"
    stl = "stl"
    blk = "blk"
    min = "min"
    double_double = "double_double"


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint(
            "player_id", "game_id", "release_id", "kind", "feature_snapshot_sha256",
            name="uq_predictions_snapshot",
        ),
        CheckConstraint(
            "kind = 'backtest' OR data_cutoff_at <= created_at", name="cutoff_before_creation"
        ),
        CheckConstraint(
            "double_double_probability IS NULL OR "
            "(double_double_probability >= 0 AND double_double_probability <= 1)",
            name="probability_range",
        ),
        Index("ix_predictions_player_created", "player_id", "created_at"),
        Index("ix_predictions_game", "game_id"),
        Index("ix_predictions_release_kind", "release_id", "kind"),
    )  # fmt: skip

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="RESTRICT"))
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id", ondelete="RESTRICT"))
    release_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("model_releases.id", ondelete="RESTRICT")
    )
    kind: Mapped[PredictionKind] = mapped_column(pg_enum(PredictionKind, "prediction_kind"))
    status: Mapped[PredictionStatus] = mapped_column(pg_enum(PredictionStatus, "prediction_status"))
    feature_schema_version: Mapped[str] = mapped_column(String(64))
    feature_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    feature_snapshot_sha256: Mapped[str] = mapped_column(String(64))
    explanation: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    data_cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = utcnow_column()
    double_double_probability: Mapped[float | None] = mapped_column(Float)
    supersedes_prediction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("predictions.id", ondelete="RESTRICT")
    )


class PredictionValue(Base):
    __tablename__ = "prediction_values"
    __table_args__ = (
        CheckConstraint("lower <= point AND point <= upper", name="interval_contains_point"),
    )

    prediction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("predictions.id", ondelete="RESTRICT"), primary_key=True
    )
    stat: Mapped[PredictedStat] = mapped_column(
        pg_enum(PredictedStat, "predicted_stat"), primary_key=True
    )
    point: Mapped[float] = mapped_column(Float)
    lower: Mapped[float] = mapped_column(Float)
    upper: Mapped[float] = mapped_column(Float)
    interval_level: Mapped[Decimal] = mapped_column(Numeric(3, 2))


class PredictionEvaluation(Base):
    __tablename__ = "prediction_evaluations"
    __table_args__ = (
        ForeignKeyConstraint(["prediction_id"], ["predictions.id"], ondelete="RESTRICT"),
    )

    prediction_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    stat: Mapped[EvaluatedStat] = mapped_column(
        pg_enum(EvaluatedStat, "evaluated_stat"), primary_key=True
    )
    actual: Mapped[float] = mapped_column(Float)
    abs_error: Mapped[float] = mapped_column(Float)
    within_interval: Mapped[bool | None] = mapped_column(Boolean)
    evaluated_at: Mapped[datetime] = utcnow_column()
