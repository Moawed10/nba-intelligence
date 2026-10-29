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
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import Context
from app.api.errors import ApiError, not_found
from app.ml.conformal import MondrianConformal
from app.ml.inference import ActiveRelease, snapshot_hash
from app.ml.team_model import MIN_PRIOR_GAMES, TEAM_FEATURES, TEAM_GAMES_SQL, team_frame
from app.models import Game, GamePrediction
from app.schemas.predictions import GameForecast, GameForecastResult, TeamScore, Unavailable
from app.services.prediction_lifecycle import (
    inference_slot,
    model_unavailable,
    serving_release,
    started,
)

HISTORY_SQL = TEAM_GAMES_SQL + " AND t.team_id IN (:home, :away) AND g.game_date < :before"
INTERVAL_LEVEL = 0.8


def _snapshot(session: Session, game: Game) -> tuple[dict[str, float | None], int]:
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
    frame = team_frame(pd.concat([history, target], ignore_index=True))
    rows = frame[frame["game_id"] == game.id].set_index("team_id")
    home, away = rows.loc[game.home_team_id], rows.loc[game.away_team_id]
    snapshot = {
        f"{side}_{name}": None if pd.isna(row[name]) else float(row[name])
        for side, row in (("home", home), ("away", away))
        for name in TEAM_FEATURES
    }
    return snapshot, int(min(home["prior_games"], away["prior_games"]))


def _predict(release: ActiveRelease, snapshot: dict[str, float | None]) -> dict[str, float]:
    X = pd.DataFrame(
        [[math.nan if (v := snapshot[f"{side}_{n}"]) is None else v for n in TEAM_FEATURES]
         for side in ("home", "away")],
        columns=list(TEAM_FEATURES),
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

    snapshot, prior = _snapshot(session, game)
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
    previous = session.scalar(
        select(GamePrediction.id).where(*key).order_by(GamePrediction.created_at.desc()).limit(1)
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


def _out(row: GamePrediction, game: Game, version: str) -> GameForecast:
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
        forecast = _out(row, ctx.session.get_one(Game, game_id), version)
        out.append(GameForecastResult(game_id=game_id, forecast=forecast, unavailable=None))
    return out
