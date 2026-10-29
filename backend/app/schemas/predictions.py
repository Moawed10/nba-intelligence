import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


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
    values: list[PredictedValue]
    explanation: dict[str, Any] | None
