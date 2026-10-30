"""Prediction API: create through the lifecycle service, read back with derived freshness."""

import uuid

from sqlalchemy import exists, select
from sqlalchemy.orm import aliased

from app.api.deps import Context
from app.api.errors import ApiError, not_found
from app.ml.artifacts import ArtifactMismatch
from app.ml.inference import ActiveRelease, active_release
from app.models import (
    Game,
    ModelRelease,
    Player,
    PlayerGameStats,
    Prediction,
    PredictionEvaluation,
    PredictionKind,
    PredictionValue,
    Team,
)
from app.models.predictions import PredictedStat
from app.schemas.predictions import (
    PredictedValue,
    PredictionExplanation,
    Unavailable,
    UpcomingForecast,
)
from app.schemas.predictions import Prediction as PredictionOut
from app.schemas.resources import HistoryEntry, HistoryValue, PredictionHistory
from app.services import games as games_service
from app.services.common import team_ref
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


def explorer(ctx: Context, player_id: int, kind: PredictionKind, limit: int) -> PredictionHistory:
    """A player's stored predictions of one kind, newest game first, each next to the result."""
    player = ctx.session.get(Player, player_id)
    if player is None:
        raise not_found("player", player_id)
    newer = aliased(Prediction)  # a later forecast replacing this one
    team_in_game = (
        select(PlayerGameStats.team_id)
        .where(
            PlayerGameStats.game_id == Prediction.game_id,
            PlayerGameStats.player_id == Prediction.player_id,
        )  # fmt: skip
        .scalar_subquery()
    )
    rows = ctx.session.execute(
        select(Prediction, Game, ModelRelease.version, team_in_game)
        .join(Game, Game.id == Prediction.game_id)
        .join(ModelRelease, ModelRelease.id == Prediction.release_id)
        .where(
            Prediction.player_id == player_id,
            Prediction.kind == kind,
            ~exists().where(newer.supersedes_prediction_id == Prediction.id),
        )  # fmt: skip
        .order_by(Game.game_date.desc(), Prediction.created_at.desc())
        .limit(limit)
    ).all()
    ids = [r[0].id for r in rows]
    values = ctx.session.scalars(
        select(PredictionValue).where(PredictionValue.prediction_id.in_(ids))
    )
    evaluations = {
        (e.prediction_id, e.stat.value): e
        for e in ctx.session.scalars(
            select(PredictionEvaluation).where(PredictionEvaluation.prediction_id.in_(ids))
        )
    }
    by_prediction: dict[uuid.UUID, dict[str, HistoryValue]] = {}
    for v in values:
        e = evaluations.get((v.prediction_id, v.stat.value))
        by_prediction.setdefault(v.prediction_id, {})[v.stat.value] = HistoryValue(
            point=v.point, lower=v.lower, upper=v.upper,
            actual=e.actual if e else None, within_interval=e.within_interval if e else None,
        )  # fmt: skip
    teams = {t.id: t for t in ctx.session.scalars(select(Team))}
    entries = []
    for prediction, game, version, team_id in rows:
        own = team_id or player.current_team_id
        is_home = own == game.home_team_id
        opponent = teams[game.away_team_id if is_home else game.home_team_id]
        entries.append(
            HistoryEntry(
                prediction_id=str(prediction.id),
                kind=prediction.kind.value,
                release_version=version,
                game_id=game.id,
                game_date=game.game_date,
                opponent=team_ref(opponent),
                is_home=is_home,
                values=by_prediction.get(prediction.id, {}),
            )  # fmt: skip
        )
    return PredictionHistory(player_id=player_id, kind=kind.value, entries=entries)
