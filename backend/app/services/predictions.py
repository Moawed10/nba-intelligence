"""Pregame predictions: validate, infer with the active release, store append-only, read back."""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import Context
from app.api.errors import ApiError, not_found
from app.ml.artifacts import ArtifactMismatch
from app.ml.features import MIN_PRIOR_GAMES
from app.ml.inference import active_release, predict, pregame_features
from app.models import (
    Game,
    GameStatus,
    ModelRelease,
    Player,
    Prediction,
    PredictionKind,
    PredictionStatus,
    PredictionValue,
)
from app.models.predictions import PredictedStat
from app.schemas.predictions import PredictedValue
from app.schemas.predictions import Prediction as PredictionOut

HISTORY_LIMIT = 20


def _model_unavailable(message: str) -> ApiError:
    return ApiError(503, "model_unavailable", message)


def _out(session: Session, row: Prediction) -> PredictionOut:
    values = session.scalars(
        select(PredictionValue).where(PredictionValue.prediction_id == row.id)
    ).all()
    order = list(PredictedStat)
    version = session.scalar(select(ModelRelease.version).where(ModelRelease.id == row.release_id))
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
        explanation=row.explanation,
    )


def create_prediction(ctx: Context, player_id: int, game_id: str) -> tuple[PredictionOut, bool]:
    """Returns the stored prediction and whether it was created by this call.

    An identical feature snapshot for the same player, game and release returns the existing row,
    so repeats never duplicate; a changed snapshot appends a row superseding the last one.
    """
    session = ctx.session
    try:
        release = active_release(session, ctx.state.artifacts_dir)
    except (ArtifactMismatch, LookupError, FileNotFoundError) as error:
        raise _model_unavailable(f"The active model release failed verification: {error}") from None
    if release is None:
        raise _model_unavailable("No model release is serving predictions yet.")

    player = session.get(Player, player_id)
    if player is None:
        raise not_found("player", player_id)
    game = session.get(Game, game_id)
    if game is None:
        raise not_found("game", game_id)
    now = ctx.now
    if game.status != GameStatus.scheduled or (
        game.tipoff_at is not None and game.tipoff_at <= now
    ):
        raise ApiError(409, "game_already_started", "Pregame predictions close at tip-off.")
    team_id = player.current_team_id
    if team_id not in (game.home_team_id, game.away_team_id):
        raise ApiError(422, "invalid_matchup", "This player's current team is not in this game.")

    is_home = team_id == game.home_team_id
    features = pregame_features(
        session,
        player_id=player_id,
        team_id=team_id,
        opponent_id=game.away_team_id if is_home else game.home_team_id,
        is_home=is_home,
        game_id=game.id,
        game_date=game.game_date,
        season_id=game.season_id,
    )
    forecast = predict(release, features)
    if not forecast.eligible:
        raise ApiError(
            422,
            "insufficient_data",
            f"Forecasts need at least {MIN_PRIOR_GAMES} games this season or last; "
            f"this player has {forecast.prior_games}.",
        )

    key = (
        Prediction.player_id == player_id,
        Prediction.game_id == game_id,
        Prediction.release_id == release.id,
        Prediction.kind == PredictionKind.pregame,
    )
    same_snapshot = select(Prediction).where(
        *key, Prediction.feature_snapshot_sha256 == forecast.snapshot_sha256
    )
    existing = session.scalar(same_snapshot)
    if existing is not None:
        return _out(session, existing), False
    previous = session.scalar(
        select(Prediction.id).where(*key).order_by(Prediction.created_at.desc())
    )

    row = Prediction(
        id=uuid.uuid4(),
        player_id=player_id,
        game_id=game_id,
        release_id=release.id,
        kind=PredictionKind.pregame,
        status=PredictionStatus.ok,
        feature_schema_version=release.feature_schema_version,
        feature_snapshot=forecast.snapshot,
        feature_snapshot_sha256=forecast.snapshot_sha256,
        explanation=forecast.explanation,
        data_cutoff_at=min(now, game.tipoff_at) if game.tipoff_at else now,
        created_at=now,
        double_double_probability=forecast.double_double_probability,
        supersedes_prediction_id=previous,
    )
    session.add(row)
    session.flush()
    level = Decimal(str(round(forecast.interval_level, 2)))
    session.add_all(
        PredictionValue(
            prediction_id=row.id,
            stat=PredictedStat(stat),
            point=point,
            lower=lower,
            upper=upper,
            interval_level=level,
        )  # fmt: skip
        for stat, (point, lower, upper) in forecast.values.items()
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.scalar(same_snapshot)
        if existing is None:
            raise
        return _out(session, existing), False
    return _out(session, row), True


def get_prediction(ctx: Context, prediction_id: uuid.UUID) -> PredictionOut:
    row = ctx.session.get(Prediction, prediction_id)
    if row is None:
        raise not_found("prediction", prediction_id)
    return _out(ctx.session, row)


def history(ctx: Context, player_id: int, game_id: str | None) -> list[PredictionOut]:
    """Newest first, superseded rows included, so every stored forecast stays visible."""
    query = select(Prediction).where(Prediction.player_id == player_id)
    if game_id:
        query = query.where(Prediction.game_id == game_id)
    rows = ctx.session.scalars(
        query.order_by(Prediction.created_at.desc()).limit(HISTORY_LIMIT)
    ).all()
    return [_out(ctx.session, r) for r in rows]
