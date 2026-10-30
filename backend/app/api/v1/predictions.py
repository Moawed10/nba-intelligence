import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.deps import Ctx
from app.models import PredictionKind
from app.schemas.predictions import (
    GameForecastRequest,
    GameForecastResult,
    Prediction,
    PredictionExplanation,
    PredictionRequest,
    UpcomingForecast,
    UpcomingRequest,
)
from app.schemas.resources import PredictionHistory
from app.services import game_forecasts, predictions

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.post("", response_model=Prediction, status_code=201)
def create_prediction(ctx: Ctx, body: PredictionRequest, response: Response) -> Prediction:
    """Pregame forecast for a player in a scheduled game; repeating it with unchanged data returns
    the stored prediction (200) instead of creating another."""
    prediction, created = predictions.create_prediction(ctx, body.player_id, body.game_id)
    response.status_code = 201 if created else 200
    return prediction


@router.post("/upcoming", response_model=list[UpcomingForecast])
def upcoming_forecasts(ctx: Ctx, body: UpcomingRequest) -> list[UpcomingForecast]:
    """Forecast every game a player has in the next `days` days (stored, reused while current)."""
    return predictions.upcoming(ctx, body.player_id, body.days)


@router.post("/games", response_model=list[GameForecastResult])
def game_forecasts_(ctx: Ctx, body: GameForecastRequest) -> list[GameForecastResult]:
    """Predicted final score and home win chance for scheduled games (stored, reused while the
    inputs are unchanged); a game that can't be forecast says why."""
    return game_forecasts.forecasts(ctx, body.game_ids)


@router.get("/history", response_model=PredictionHistory)
def prediction_history(
    ctx: Ctx,
    player_id: Annotated[int, Query(ge=1)],
    kind: PredictionKind = PredictionKind.backtest,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PredictionHistory:
    """A player's stored predictions next to what happened. "backtest" rows were made after the
    fact by models that never saw that season; "pregame" rows were stored before tip-off."""
    ctx.always_revalidate()
    return predictions.explorer(ctx, player_id, kind, limit)


@router.get("", response_model=list[Prediction])
def list_predictions(
    ctx: Ctx,
    player_id: Annotated[int, Query(ge=1)],
    game_id: Annotated[str | None, Query(pattern=r"^\d{10}$")] = None,
) -> list[Prediction]:
    return predictions.history(ctx, player_id, game_id)


@router.get("/{prediction_id}", response_model=Prediction)
def get_prediction(ctx: Ctx, prediction_id: uuid.UUID) -> Prediction:
    return predictions.get_prediction(ctx, prediction_id)


@router.get("/{prediction_id}/explanation", response_model=PredictionExplanation)
def get_explanation(ctx: Ctx, prediction_id: uuid.UUID) -> PredictionExplanation:
    ctx.always_revalidate()
    return predictions.explanation(ctx, prediction_id)
