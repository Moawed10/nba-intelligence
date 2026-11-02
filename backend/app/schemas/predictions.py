import re
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

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


class GameForecastRequest(BaseModel):
    game_ids: list[str] = Field(min_length=1, max_length=30)

    @field_validator("game_ids")
    @classmethod
    def _ids(cls, value: list[str]) -> list[str]:
        if any(not re.fullmatch(r"\d{10}", v) for v in value):
            raise ValueError("game ids are 10 digits")
        return list(dict.fromkeys(value))


class TeamScore(BaseModel):
    team_id: int
    points: float
    lower: float
    upper: float


class GameForecast(BaseModel):
    """Both teams' expected points and the home side's win chance before tip-off."""

    id: uuid.UUID
    game_id: str
    release_version: str
    home: TeamScore
    away: TeamScore
    home_win_probability: float
    interval_level: float
    created_at: datetime
    data_cutoff_at: datetime
    supersedes_prediction_id: uuid.UUID | None
    freshness: Literal["current", "stale", "invalid", "superseded", "final_pregame"]
    freshness_reason: str | None


class GameForecastEvaluation(BaseModel):
    home_abs_error: float
    away_abs_error: float
    home_within_interval: bool
    away_within_interval: bool
    winner_correct: bool
    brier: float
    evaluated_at: datetime


class GameForecastResult(BaseModel):
    """One requested game with its stored score forecast, or the reason there is none."""

    game_id: str
    forecast: GameForecast | None
    unavailable: Unavailable | None


class GameForecastReview(BaseModel):
    """The last score forecast stored before tip-off and, once the game is final, the result."""

    game_id: str
    status: str
    forecast: GameForecast | None
    home_score: int | None
    away_score: int | None
    # Whether the side given the higher win chance won; null until the game is final.
    picked_winner: bool | None
    evaluation: GameForecastEvaluation | None
