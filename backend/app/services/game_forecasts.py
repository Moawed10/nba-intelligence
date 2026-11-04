"""Pregame score forecasts for scheduled games, stored append-only (one row per input snapshot).

Both teams' rows are built exactly like training rows (app/ml/team_model.py): the scheduled game is
appended to each team's earlier final games, so its features only see games played before it.
"""

import math
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import Float, Integer, cast, exists, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.api.deps import Context
from app.api.errors import ApiError, not_found
from app.ml.conformal import MondrianConformal
from app.ml.inference import ActiveRelease, snapshot_hash, team_lines_tonight
from app.ml.team_model import MIN_PRIOR_GAMES, TEAM_FEATURES, TEAM_GAMES_SQL, team_frame
from app.models import (
    Game,
    GamePrediction,
    GamePredictionEvaluation,
    GameStatus,
    ModelRelease,
)
from app.schemas.predictions import (
    GameForecast,
    GameForecastEvaluation,
    GameForecastResult,
    GameForecastReview,
    TeamScore,
    Unavailable,
)
from app.services.prediction_lifecycle import (
    REFRESH_WINDOW,
    Freshness,
    FreshnessState,
    inference_slot,
    model_unavailable,
    serving_release,
    started,
)

HISTORY_SQL = TEAM_GAMES_SQL + " AND t.team_id IN (:home, :away) AND g.game_date < :before"
INTERVAL_LEVEL = 0.8


def _features(release: ActiveRelease) -> tuple[str, ...]:
    """The inputs this release's score model was trained on; older releases have fewer."""
    return tuple(release.team["team_pts"].get("features") or TEAM_FEATURES)


def _snapshot(
    session: Session, game: Game, features: tuple[str, ...]
) -> tuple[dict[str, float | None], int]:
    """Home and away feature values keyed `home_<feature>` / `away_<feature>`, and the smaller
    number of earlier games either team has."""
    history = pd.read_sql(
        text(HISTORY_SQL),
        session.connection(),
        params={"home": game.home_team_id, "away": game.away_team_id, "before": game.game_date},
        parse_dates=["game_date"],
    )
    target = pd.DataFrame(
        [
            {
                "game_id": game.id,
                "game_date": pd.Timestamp(game.game_date),
                "season_id": game.season_id,
                "team_id": team,
                "opponent_id": opponent,
                "is_home": home,
                "minutes": 240.0,
            }  # fmt: skip
            for team, opponent, home in (
                (game.home_team_id, game.away_team_id, True),
                (game.away_team_id, game.home_team_id, False),
            )
        ]
    )
    tonight = team_lines_tonight(
        session,
        team_id=game.home_team_id,
        opponent_id=game.away_team_id,
        game_id=game.id,
        game_date=game.game_date,
        season_id=game.season_id,
    )
    frame = team_frame(pd.concat([history, target], ignore_index=True), tonight)
    rows = frame[frame["game_id"] == game.id].set_index("team_id")
    home, away = rows.loc[game.home_team_id], rows.loc[game.away_team_id]
    snapshot = {
        f"{side}_{name}": None if pd.isna(row[name]) else float(row[name])
        for side, row in (("home", home), ("away", away))
        for name in features
    }
    return snapshot, int(min(home["prior_games"], away["prior_games"]))


def _predict(release: ActiveRelease, snapshot: dict[str, float | None]) -> dict[str, float]:
    features = _features(release)
    X = pd.DataFrame(
        [[math.nan if (v := snapshot[f"{side}_{n}"]) is None else v for n in features]
         for side in ("home", "away")],
        columns=list(features),
    )  # fmt: skip
    points = release.team["team_pts"]
    predicted = np.maximum(0, points["model"].predict(X))
    lower, upper = MondrianConformal.from_dict(points["conformal"]).interval(predicted, predicted)
    margin = np.array([[predicted[0] - predicted[1]]])
    win = release.team["home_win"]["model"]
    return {
        "home_pts": float(predicted[0]),
        "home_lower": float(lower[0]),
        "home_upper": float(upper[0]),
        "away_pts": float(predicted[1]),
        "away_lower": float(lower[1]),
        "away_upper": float(upper[1]),
        "home_win_probability": float(win.predict_proba(margin)[0, 1]),
    }


def forecast_game(
    session: Session, artifacts_dir: Path, now: datetime, game_id: str
) -> tuple[GamePrediction, str, bool]:
    """Stored score forecast for a scheduled game, the release version, and whether this call
    created it. An unchanged snapshot returns the existing row; a changed one supersedes it."""
    release = serving_release(session, artifacts_dir)
    if "team_pts" not in release.team or "home_win" not in release.team:
        raise model_unavailable("The serving release has no game score model.")
    game = session.get(Game, game_id)
    if game is None:
        raise not_found("game", game_id)
    if started(game, now):
        raise ApiError(409, "game_already_started", "Pregame forecasts close at tip-off.")

    snapshot, prior = _snapshot(session, game, _features(release))
    if prior < MIN_PRIOR_GAMES:
        raise ApiError(
            422,
            "insufficient_data",
            f"Score forecasts need {MIN_PRIOR_GAMES} earlier games for each team; "
            f"one team has {prior}.",
        )
    digest = snapshot_hash(snapshot)
    key = (GamePrediction.game_id == game_id, GamePrediction.release_id == release.id)
    same = select(GamePrediction).where(*key, GamePrediction.feature_snapshot_sha256 == digest)
    if (existing := session.scalar(same)) is not None:
        return existing, release.version, False

    with inference_slot():
        values = _predict(release, snapshot)
    newer = aliased(GamePrediction)
    previous = session.scalar(
        select(GamePrediction.id)
        .where(*key, ~exists().where(newer.supersedes_prediction_id == GamePrediction.id))
        .order_by(GamePrediction.created_at.desc())
        .limit(1)
    )
    row = GamePrediction(
        id=uuid.uuid4(),
        game_id=game_id,
        release_id=release.id,
        **values,
        feature_snapshot=snapshot,
        feature_snapshot_sha256=digest,
        data_cutoff_at=now,
        created_at=now,
        supersedes_prediction_id=previous,
    )
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        # A concurrent request stored the same snapshot first.
        session.rollback()
        if (existing := session.scalar(same)) is None:
            raise
        return existing, release.version, False
    return row, release.version, True


def freshness(
    session: Session, row: GamePrediction, game: Game, now: datetime, release: ActiveRelease | None
) -> FreshnessState:
    child = aliased(GamePrediction)
    if session.scalar(select(exists().where(child.supersedes_prediction_id == row.id))):
        return FreshnessState(Freshness.superseded, "A newer forecast replaced this one.")
    if game.status in (GameStatus.postponed, GameStatus.cancelled):
        return FreshnessState(Freshness.invalid, f"The game was {game.status.value}.")
    if started(game, now):
        return FreshnessState(Freshness.final_pregame, "Last forecast made before tip-off.")
    if release is None or release.id != row.release_id:
        return FreshnessState(Freshness.stale, "A different model release is now serving.")
    snapshot, _ = _snapshot(session, game, _features(release))
    if snapshot_hash(snapshot) != row.feature_snapshot_sha256:
        return FreshnessState(Freshness.stale, "New games or injury news since this forecast.")
    return FreshnessState(Freshness.current)


def _out(row: GamePrediction, game: Game, version: str, state: FreshnessState) -> GameForecast:
    return GameForecast(
        id=row.id,
        game_id=row.game_id,
        release_version=version,
        home=TeamScore(
            team_id=game.home_team_id,
            points=row.home_pts,
            lower=row.home_lower,
            upper=row.home_upper,
        ),
        away=TeamScore(
            team_id=game.away_team_id,
            points=row.away_pts,
            lower=row.away_lower,
            upper=row.away_upper,
        ),
        home_win_probability=row.home_win_probability,
        interval_level=INTERVAL_LEVEL,
        created_at=row.created_at,
        data_cutoff_at=row.data_cutoff_at,
        supersedes_prediction_id=row.supersedes_prediction_id,
        freshness=state.state.value,
        freshness_reason=state.reason,
    )


def forecasts(ctx: Context, game_ids: list[str]) -> list[GameForecastResult]:
    """Score forecasts for the requested games; a game that can't be forecast says why."""
    out: list[GameForecastResult] = []
    for game_id in game_ids:
        try:
            row, version, _ = forecast_game(ctx.session, ctx.state.artifacts_dir, ctx.now, game_id)
        except ApiError as error:
            ctx.session.rollback()
            if error.status == 503:
                raise
            reason = Unavailable(code=error.code, message=error.message)
            out.append(GameForecastResult(game_id=game_id, forecast=None, unavailable=reason))
            continue
        current = FreshnessState(Freshness.current)
        forecast = _out(row, ctx.session.get_one(Game, game_id), version, current)
        out.append(GameForecastResult(game_id=game_id, forecast=forecast, unavailable=None))
    return out


def store_upcoming(session: Session, artifacts_dir: Path, now: datetime) -> dict[str, int]:
    """Store a score forecast for every scheduled game tipping off in the refresh window, so each
    game has a pregame prediction to compare with its final score. Same inputs store nothing."""
    games = session.scalars(
        select(Game.id).where(
            Game.status == GameStatus.scheduled,
            Game.tipoff_at > now,
            Game.tipoff_at <= now + REFRESH_WINDOW,
        )
    ).all()
    counts = {"game_forecasts": 0, "game_forecasts_skipped": 0}
    for game_id in games:
        try:
            _, _, created = forecast_game(session, artifacts_dir, now, game_id)
        except ApiError:
            session.rollback()
            counts["game_forecasts_skipped"] += 1
            continue
        counts["game_forecasts"] += created
    return counts


def review(ctx: Context, game_id: str) -> GameForecastReview:
    """The last score forecast stored before tip-off, next to the final score once there is one."""
    game = ctx.session.get(Game, game_id)
    if game is None:
        raise not_found("game", game_id)
    newer = aliased(GamePrediction)
    row = ctx.session.execute(
        select(GamePrediction, ModelRelease.version)
        .join(ModelRelease, ModelRelease.id == GamePrediction.release_id)
        .where(
            GamePrediction.game_id == game_id,
            ~exists().where(newer.supersedes_prediction_id == GamePrediction.id),
        )
        .order_by(GamePrediction.created_at.desc())
        .limit(1)
    ).first()
    final = game.status == GameStatus.final and game.home_score is not None
    forecast = None
    evaluation = None
    if row:
        try:
            release = serving_release(ctx.session, ctx.state.artifacts_dir)
        except ApiError:
            release = None
        state = freshness(ctx.session, row[0], game, ctx.now, release)
        forecast = _out(row[0], game, row[1], state)
        stored = ctx.session.get(GamePredictionEvaluation, row[0].id)
        if stored is not None:
            evaluation = GameForecastEvaluation(
                home_abs_error=stored.home_abs_error,
                away_abs_error=stored.away_abs_error,
                home_within_interval=stored.home_within_interval,
                away_within_interval=stored.away_within_interval,
                winner_correct=stored.winner_correct,
                brier=stored.brier,
                evaluated_at=stored.evaluated_at,
            )
    picked = None
    if forecast and final:
        predicted_home = forecast.home_win_probability >= 0.5
        picked = predicted_home == (game.home_score > game.away_score)  # type: ignore[operator]
    return GameForecastReview(
        game_id=game_id,
        status=game.status.value,
        forecast=forecast,
        home_score=game.home_score if final else None,
        away_score=game.away_score if final else None,
        picked_winner=picked,
        evaluation=evaluation,
    )


def score_game(session: Session, game_id: str, now: datetime) -> int:
    game = session.get(Game, game_id)
    if (
        game is None
        or game.status != GameStatus.final
        or game.home_score is None
        or game.away_score is None
    ):
        return 0
    rows = session.scalars(select(GamePrediction).where(GamePrediction.game_id == game_id)).all()
    home_won = game.home_score > game.away_score
    for row in rows:
        values = {
            "forecast_id": row.id,
            "home_actual": game.home_score,
            "away_actual": game.away_score,
            "home_abs_error": abs(row.home_pts - game.home_score),
            "away_abs_error": abs(row.away_pts - game.away_score),
            "home_within_interval": row.home_lower <= game.home_score <= row.home_upper,
            "away_within_interval": row.away_lower <= game.away_score <= row.away_upper,
            "winner_correct": (row.home_win_probability >= 0.5) == home_won,
            "brier": (row.home_win_probability - float(home_won)) ** 2,
            "evaluated_at": now,
        }
        stmt = insert(GamePredictionEvaluation).values(values)
        session.execute(
            stmt.on_conflict_do_update(
                index_elements=["forecast_id"],
                set_={k: stmt.excluded[k] for k in values if k != "forecast_id"},
            )
        )
    return len(rows)


def score_pending(session: Session, now: datetime) -> int:
    evaluation = GamePredictionEvaluation
    games = session.scalars(
        select(GamePrediction.game_id)
        .join(Game, Game.id == GamePrediction.game_id)
        .outerjoin(evaluation, evaluation.forecast_id == GamePrediction.id)
        .where(
            Game.status == GameStatus.final,
            Game.stats_finalized_at.is_not(None),
            Game.home_score.is_not(None),
            or_(
                evaluation.forecast_id.is_(None),
                evaluation.home_actual != Game.home_score,
                evaluation.away_actual != Game.away_score,
            ),
        )
        .distinct()
    ).all()
    return sum(score_game(session, game_id, now) for game_id in games)


def live_accuracy(session: Session, release_id: uuid.UUID) -> dict | None:
    evaluation = GamePredictionEvaluation
    newer = aliased(GamePrediction)
    row = session.execute(
        select(
            func.count(),
            func.avg((evaluation.home_abs_error + evaluation.away_abs_error) / 2),
            func.avg(
                (
                    cast(cast(evaluation.home_within_interval, Integer), Float)
                    + cast(cast(evaluation.away_within_interval, Integer), Float)
                )
                / 2
            ),
            func.avg(evaluation.brier),
            func.avg(cast(cast(evaluation.winner_correct, Integer), Float)),
        )
        .join(GamePrediction, GamePrediction.id == evaluation.forecast_id)
        .where(
            GamePrediction.release_id == release_id,
            ~exists().where(newer.supersedes_prediction_id == GamePrediction.id),
        )
    ).one()
    if not row[0]:
        return None
    return {
        "games": row[0],
        "points_mae": row[1],
        "interval_coverage": row[2],
        "brier": row[3],
        "winner_accuracy": row[4],
    }
