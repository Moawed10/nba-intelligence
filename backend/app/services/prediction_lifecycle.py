"""Pregame forecasts after creation: freshness, refresh before tip-off, and scoring after the game.

docs/data-synchronization.md#prediction-freshness. Rows are never modified: a refresh appends a
row that supersedes the last one, and scoring writes `prediction_evaluations` only.
"""

import enum
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import Float, Integer, exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.api.errors import ApiError, not_found
from app.ml.artifacts import ArtifactMismatch
from app.ml.features import MIN_PRIOR_GAMES, TARGETS
from app.ml.inference import ActiveRelease, active_release, predict, pregame_features
from app.ml.inference import snapshot_hash as hash_snapshot
from app.models import (
    Game,
    GameStatus,
    Player,
    PlayerGameStats,
    Prediction,
    PredictionEvaluation,
    PredictionKind,
    PredictionStatus,
    PredictionValue,
)
from app.models.predictions import EvaluatedStat, PredictedStat

REFRESH_WINDOW = timedelta(hours=48)
# At most this many forecasts are computed at once; others wait up to INFERENCE_WAIT_SECONDS.
INFERENCE_CONCURRENCY = 4
INFERENCE_WAIT_SECONDS = 10
_inference_slots = threading.BoundedSemaphore(INFERENCE_CONCURRENCY)


class Freshness(enum.StrEnum):
    current = "current"
    stale = "stale"
    invalid = "invalid"
    superseded = "superseded"
    final_pregame = "final_pregame"


@dataclass(frozen=True)
class FreshnessState:
    state: Freshness
    reason: str | None = None


@contextmanager
def inference_slot() -> Iterator[None]:
    if not _inference_slots.acquire(timeout=INFERENCE_WAIT_SECONDS):
        raise ApiError(503, "inference_busy", "Forecasting is busy. Try again in a moment.")
    try:
        yield
    finally:
        _inference_slots.release()


def model_unavailable(message: str) -> ApiError:
    return ApiError(503, "model_unavailable", message)


def serving_release(session: Session, artifacts_dir: Path) -> ActiveRelease:
    try:
        release = active_release(session, artifacts_dir)
    except (ArtifactMismatch, LookupError, FileNotFoundError) as error:
        raise model_unavailable(f"The active model release failed verification: {error}") from None
    if release is None:
        raise model_unavailable("No model release is serving predictions yet.")
    return release


def _features(session: Session, player: Player, game: Game):
    is_home = player.current_team_id == game.home_team_id
    return pregame_features(
        session,
        player_id=player.id,
        team_id=player.current_team_id,
        opponent_id=game.away_team_id if is_home else game.home_team_id,
        is_home=is_home,
        game_id=game.id,
        game_date=game.game_date,
        season_id=game.season_id,
    )


def started(game: Game, now: datetime) -> bool:
    return game.status != GameStatus.scheduled or (
        game.tipoff_at is not None and game.tipoff_at <= now
    )


def forecast(
    session: Session, artifacts_dir: Path, now: datetime, player_id: int, game_id: str
) -> tuple[Prediction, bool]:
    """Stored forecast for a player in a scheduled game, and whether this call created it.

    An identical feature snapshot for the same player, game and release returns the existing row,
    so repeats never duplicate; a changed snapshot appends a row superseding the last one.
    """
    release = serving_release(session, artifacts_dir)
    player = session.get(Player, player_id)
    if player is None:
        raise not_found("player", player_id)
    game = session.get(Game, game_id)
    if game is None:
        raise not_found("game", game_id)
    if started(game, now):
        raise ApiError(409, "game_already_started", "Pregame predictions close at tip-off.")
    if player.current_team_id not in (game.home_team_id, game.away_team_id):
        raise ApiError(422, "invalid_matchup", "This player's current team is not in this game.")

    with inference_slot():
        result = predict(release, _features(session, player, game))
    if not result.eligible:
        raise ApiError(
            422,
            "insufficient_data",
            f"Forecasts need at least {MIN_PRIOR_GAMES} games this season or last; "
            f"this player has {result.prior_games}.",
        )

    key = (
        Prediction.player_id == player_id,
        Prediction.game_id == game_id,
        Prediction.release_id == release.id,
        Prediction.kind == PredictionKind.pregame,
    )
    same_snapshot = select(Prediction).where(
        *key, Prediction.feature_snapshot_sha256 == result.snapshot_sha256
    )
    existing = session.scalar(same_snapshot)
    if existing is not None:
        return existing, False
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
        feature_snapshot=result.snapshot,
        feature_snapshot_sha256=result.snapshot_sha256,
        explanation=result.explanation,
        data_cutoff_at=min(now, game.tipoff_at) if game.tipoff_at else now,
        created_at=now,
        double_double_probability=result.double_double_probability,
        supersedes_prediction_id=previous,
    )
    session.add(row)
    session.flush()
    level = Decimal(str(round(result.interval_level, 2)))
    session.add_all(
        PredictionValue(
            prediction_id=row.id,
            stat=PredictedStat(stat),
            point=point,
            lower=lower,
            upper=upper,
            interval_level=level,
        )  # fmt: skip
        for stat, (point, lower, upper) in result.values.items()
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.scalar(same_snapshot)
        if existing is None:
            raise
        return existing, False
    return row, True


def freshness(
    session: Session, row: Prediction, now: datetime, release: ActiveRelease | None
) -> FreshnessState:
    """Derived state of a stored forecast; the row itself never changes."""
    child = aliased(Prediction)
    if session.scalar(select(exists().where(child.supersedes_prediction_id == row.id))):
        return FreshnessState(Freshness.superseded, "A newer forecast replaced this one.")
    game = session.get(Game, row.game_id)
    if game.status in (GameStatus.postponed, GameStatus.cancelled):
        return FreshnessState(Freshness.invalid, f"The game was {game.status.value}.")
    if started(game, now):
        return FreshnessState(Freshness.final_pregame, "Last forecast made before tip-off.")
    player = session.get(Player, row.player_id)
    if player.current_team_id not in (game.home_team_id, game.away_team_id):
        return FreshnessState(Freshness.invalid, "The player's team is no longer in this game.")
    if release is None or release.id != row.release_id:
        return FreshnessState(Freshness.stale, "A different model release is now serving.")
    snapshot = predict(release, _features(session, player, game)).snapshot
    if hash_snapshot(snapshot) != row.feature_snapshot_sha256:
        return FreshnessState(Freshness.stale, "New games have been played since this forecast.")
    return FreshnessState(Freshness.current)


def refresh_due(session: Session, artifacts_dir: Path, now: datetime) -> dict[str, int]:
    """Re-forecast stale predictions for games in the next 48 hours, only for players someone
    already asked about. A model change marks forecasts stale but does not regenerate them."""
    counts = {"checked": 0, "refreshed": 0, "skipped": 0}
    try:
        release = serving_release(session, artifacts_dir)
    except ApiError:
        return counts
    child = aliased(Prediction)
    rows = session.scalars(
        select(Prediction)
        .join(Game, Game.id == Prediction.game_id)
        .where(
            Prediction.kind == PredictionKind.pregame,
            Prediction.release_id == release.id,
            ~exists().where(child.supersedes_prediction_id == Prediction.id),
            Game.status == GameStatus.scheduled,
            Game.tipoff_at > now,
            Game.tipoff_at <= now + REFRESH_WINDOW,
        )
    ).all()
    for row in rows:
        counts["checked"] += 1
        if freshness(session, row, now, release).state != Freshness.stale:
            continue
        try:
            _, created = forecast(session, artifacts_dir, now, row.player_id, row.game_id)
        except ApiError:
            session.rollback()
            counts["skipped"] += 1
            continue
        counts["refreshed"] += created
    return counts


def _double_double(line: PlayerGameStats) -> int:
    return int(sum(getattr(line, s) >= 10 for s in ("pts", "reb", "ast", "stl", "blk")) >= 2)


def _actual(line: PlayerGameStats, stat: str) -> float:
    return float(line.minutes if stat == "min" else getattr(line, stat))


def score_game(session: Session, game_id: str, now: datetime) -> int:
    """Write evaluations for every pregame forecast of a final game. Re-scoring after a source
    correction overwrites evaluations, never the forecast. Players who did not play are skipped."""
    game = session.get(Game, game_id)
    if game is None or game.status != GameStatus.final:
        return 0
    lines = {
        line.player_id: line
        for line in session.scalars(
            select(PlayerGameStats).where(
                PlayerGameStats.game_id == game_id, PlayerGameStats.minutes > 0
            )
        )
    }
    rows = session.scalars(
        select(Prediction).where(
            Prediction.game_id == game_id, Prediction.kind == PredictionKind.pregame
        )
    ).all()
    written = 0
    for row in rows:
        line = lines.get(row.player_id)
        if line is None:
            continue
        evaluations = []
        values = session.scalars(
            select(PredictionValue).where(PredictionValue.prediction_id == row.id)
        )
        for v in values:
            actual = _actual(line, v.stat.value)
            evaluations.append({
                "prediction_id": row.id, "stat": EvaluatedStat(v.stat.value), "actual": actual,
                "abs_error": abs(v.point - actual), "within_interval": v.lower <= actual <= v.upper,
                "evaluated_at": now,
            })  # fmt: skip
        if row.double_double_probability is not None:
            actual = _double_double(line)
            evaluations.append({
                "prediction_id": row.id, "stat": EvaluatedStat.double_double,
                "actual": float(actual), "abs_error": abs(row.double_double_probability - actual),
                "within_interval": None, "evaluated_at": now,
            })  # fmt: skip
        stmt = insert(PredictionEvaluation).values(evaluations)
        updated = ("actual", "abs_error", "within_interval", "evaluated_at")
        session.execute(
            stmt.on_conflict_do_update(
                index_elements=["prediction_id", "stat"],
                set_={c: stmt.excluded[c] for c in updated},
            )
        )
        written += len(evaluations)
    return written


def score_pending(session: Session, now: datetime) -> int:
    """Score final games with stable box scores whose forecasts have no evaluations yet."""
    scored = exists().where(PredictionEvaluation.prediction_id == Prediction.id)
    games = session.scalars(
        select(Prediction.game_id)
        .join(Game, Game.id == Prediction.game_id)
        .where(Game.status == GameStatus.final, Game.stats_finalized_at.is_not(None), ~scored)
        .distinct()
    ).all()
    return sum(score_game(session, game_id, now) for game_id in games)


def live_accuracy(session: Session, release_id: uuid.UUID) -> dict:
    """Accuracy of each player-game's final pregame forecast (the one not superseded)."""
    child = aliased(Prediction)
    final = (
        select(Prediction.id, Prediction.game_id)
        .where(
            Prediction.release_id == release_id,
            Prediction.kind == PredictionKind.pregame,
            ~exists().where(child.supersedes_prediction_id == Prediction.id),
        )
        .subquery()
    )
    error = PredictionEvaluation.abs_error
    rows = session.execute(
        select(
            PredictionEvaluation.stat,
            func.count(),
            func.avg(error),
            func.avg(func.cast(func.cast(PredictionEvaluation.within_interval, Integer), Float)),
            func.avg(error * error),
        )
        .join(final, final.c.id == PredictionEvaluation.prediction_id)
        .group_by(PredictionEvaluation.stat)
    ).all()
    games = session.scalar(
        select(func.count(func.distinct(final.c.game_id))).join(
            PredictionEvaluation, PredictionEvaluation.prediction_id == final.c.id
        )
    )
    by_stat = {r[0].value: r for r in rows}
    double_double = by_stat.get("double_double")
    return {
        "games": games or 0,
        "stats": [
            {
                "stat": stat,
                "n": by_stat[stat][1],
                "mae": by_stat[stat][2],
                "interval_coverage": by_stat[stat][3],
            }  # fmt: skip
            for stat in TARGETS
            if stat in by_stat
        ],
        "double_double": (
            {"n": double_double[1], "brier": double_double[4]} if double_double else None
        ),
    }
