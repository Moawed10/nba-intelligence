"""Prediction API: create through the lifecycle service, read back with derived freshness."""

import uuid

from sqlalchemy import select

from app.api.deps import Context
from app.api.errors import ApiError, not_found
from app.ml.artifacts import ArtifactMismatch
from app.ml.inference import ActiveRelease, active_release
from app.models import ModelRelease, Player, Prediction, PredictionEvaluation, PredictionValue
from app.models.predictions import PredictedStat
from app.schemas.predictions import (
    PredictedValue,
    PredictionExplanation,
    Unavailable,
    UpcomingForecast,
)
from app.schemas.predictions import Prediction as PredictionOut
from app.services import games as games_service
from app.services.prediction_lifecycle import Freshness, FreshnessState, forecast, freshness

HISTORY_LIMIT = 20


def _release(ctx: Context) -> ActiveRelease | None:
    try:
        return active_release(ctx.session, ctx.state.artifacts_dir)
    except (ArtifactMismatch, LookupError, FileNotFoundError):
        return None


def _out(ctx: Context, row: Prediction, state: FreshnessState | None = None) -> PredictionOut:
    session = ctx.session
    values = session.scalars(
        select(PredictionValue).where(PredictionValue.prediction_id == row.id)
    ).all()
    order = list(PredictedStat)
    version = session.scalar(select(ModelRelease.version).where(ModelRelease.id == row.release_id))
    actuals = {
        e.stat.value: e.actual
        for e in session.scalars(
            select(PredictionEvaluation).where(PredictionEvaluation.prediction_id == row.id)
        )
    }
    state = state or freshness(session, row, ctx.now, _release(ctx))
    return PredictionOut(
        id=row.id,
        player_id=row.player_id,
        game_id=row.game_id,
        release_version=version or "",
        kind=row.kind.value,
        status=row.status.value,
        created_at=row.created_at,
        data_cutoff_at=row.data_cutoff_at,
        feature_schema_version=row.feature_schema_version,
        double_double_probability=row.double_double_probability,
        supersedes_prediction_id=row.supersedes_prediction_id,
        freshness=state.state.value,
        freshness_reason=state.reason,
        values=[
            PredictedValue(
                stat=v.stat.value,
                point=v.point,
                lower=v.lower,
                upper=v.upper,
                interval_level=float(v.interval_level),
            )  # fmt: skip
            for v in sorted(values, key=lambda v: order.index(v.stat))
        ],
        actuals=actuals or None,
        explanation=row.explanation,
    )


def create_prediction(ctx: Context, player_id: int, game_id: str) -> tuple[PredictionOut, bool]:
    """Returns the stored prediction and whether it was created by this call."""
    row, created = forecast(ctx.session, ctx.state.artifacts_dir, ctx.now, player_id, game_id)
    return _out(ctx, row, FreshnessState(Freshness.current) if created else None), created


def _row(ctx: Context, prediction_id: uuid.UUID) -> Prediction:
    row = ctx.session.get(Prediction, prediction_id)
    if row is None:
        raise not_found("prediction", prediction_id)
    return row


def get_prediction(ctx: Context, prediction_id: uuid.UUID) -> PredictionOut:
    return _out(ctx, _row(ctx, prediction_id))


def explanation(ctx: Context, prediction_id: uuid.UUID) -> PredictionExplanation:
    """The inputs a forecast received: highlighted averages and the full stored feature snapshot."""
    row = _row(ctx, prediction_id)
    stored = row.explanation or {}
    return PredictionExplanation(
        prediction_id=row.id,
        method=stored.get("method", "inputs"),
        inputs=stored.get("inputs", {}),
        context=stored.get("context", {}),
        features=row.feature_snapshot,
    )


def history(ctx: Context, player_id: int, game_id: str | None) -> list[PredictionOut]:
    """Newest first, superseded rows included, so every stored forecast stays visible."""
    query = select(Prediction).where(Prediction.player_id == player_id)
    if game_id:
        query = query.where(Prediction.game_id == game_id)
    rows = ctx.session.scalars(
        query.order_by(Prediction.created_at.desc()).limit(HISTORY_LIMIT)
    ).all()
    return [_out(ctx, r) for r in rows]


def upcoming(ctx: Context, player_id: int, days: int) -> list[UpcomingForecast]:
    """Forecasts for every game the player has in the next `days` days. Each stored forecast is
    reused while its inputs are unchanged, so repeating the call never duplicates rows."""
    if ctx.session.get(Player, player_id) is None:
        raise not_found("player", player_id)
    out: list[UpcomingForecast] = []
    for game in games_service.upcoming(ctx, days, player_id):
        try:
            row, _ = forecast(ctx.session, ctx.state.artifacts_dir, ctx.now, player_id, game.id)
        except ApiError as error:
            ctx.session.rollback()
            if error.status == 503 and error.code == "model_unavailable":
                raise
            reason = Unavailable(code=error.code, message=error.message)
            out.append(UpcomingForecast(game=game, prediction=None, unavailable=reason))
            continue
        current = FreshnessState(Freshness.current)
        out.append(
            UpcomingForecast(game=game, prediction=_out(ctx, row, current), unavailable=None)
        )
    return out
