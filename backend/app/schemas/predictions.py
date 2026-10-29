import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.resources import GameSummary


class PredictionRequest(BaseModel):
    player_id: int = Field(ge=1)
    game_id: str = Field(pattern=r"^\d{10}$")


class PredictedValue(BaseModel):
    stat: Literal["pts", "reb", "ast", "fg3m", "stl", "blk", "min"]
    point: float
    lower: float
    upper: float
    interval_level: float


class Prediction(BaseModel):
    id: uuid.UUID
    player_id: int
    game_id: str
    release_version: str
    kind: Literal["pregame", "backtest"]
    status: Literal["ok", "insufficient_data", "model_unavailable"]
    created_at: datetime
    data_cutoff_at: datetime
    feature_schema_version: str
    double_double_probability: float | None
    supersedes_prediction_id: uuid.UUID | None
    freshness: Literal["current", "stale", "invalid", "superseded", "final_pregame"]
    freshness_reason: str | None
    values: list[PredictedValue]
    actuals: dict[str, float] | None
    explanation: dict[str, Any] | None


class PredictionExplanation(BaseModel):
    """What the model received. These are inputs, not attributions of the model's reasoning."""

    prediction_id: uuid.UUID
    method: str
    inputs: dict[str, Any]
    context: dict[str, Any]
    features: dict[str, float | None]


class UpcomingRequest(BaseModel):
    player_id: int = Field(ge=1)
    days: int = Field(default=14, ge=1, le=14)


class Unavailable(BaseModel):
    code: str
    message: str


class UpcomingForecast(BaseModel):
    """One scheduled game with its stored forecast, or the reason there is none."""

    game: GameSummary
    prediction: Prediction | None
    unavailable: Unavailable | None
