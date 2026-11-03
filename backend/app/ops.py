from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.ml.artifacts import ArtifactMismatch
from app.ml.inference import active_release
from app.models import (
    Game,
    GamePrediction,
    GamePredictionEvaluation,
    GameStatus,
    IngestionRun,
    PlayerGameStats,
    Prediction,
    PredictionEvaluation,
    PredictionKind,
    RunStatus,
    SyncEvent,
    SyncSchedule,
)
from app.sync.freshness import Freshness, dataset_freshness

OVERDUE_AFTER = timedelta(minutes=15)
FAILURE_WINDOW = timedelta(hours=24)
SCORING_GRACE = timedelta(hours=1)
EVENT_GRACE = timedelta(minutes=15)


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


def _check(name: str, problems: list[str], healthy: str) -> Check:
    if problems:
        return Check(name, "fail", "; ".join(problems))
    return Check(name, "ok", healthy)


def overdue_sync(session: Session, now: datetime) -> Check:
    jobs = session.scalars(
        select(SyncSchedule.job).where(
            SyncSchedule.enabled, SyncSchedule.next_run_at < now - OVERDUE_AFTER
        )
    ).all()
    has_schedules = session.scalar(select(exists().where(SyncSchedule.enabled)))
    problems = [f"overdue: {job}" for job in jobs]
    if not has_schedules:
        problems.append("no sync schedules; the worker has never run")
    return _check("overdue_sync", problems, "all scheduled jobs are on time")


def failed_ingestion(session: Session, now: datetime) -> Check:
    latest = session.execute(
        select(IngestionRun.job, IngestionRun.params, IngestionRun.status)
        .where(
            IngestionRun.started_at >= now - FAILURE_WINDOW,
            IngestionRun.status != RunStatus.running,
        )
        .distinct(IngestionRun.job, IngestionRun.params)
        .order_by(IngestionRun.job, IngestionRun.params, IngestionRun.started_at.desc())
    ).all()
    problems = [f"{r.job} {r.params}: {r.status.value}" for r in latest
                if r.status != RunStatus.succeeded]  # fmt: skip
    return _check("failed_ingestion", problems, f"{len(latest)} recent job runs succeeded")


def stale_data(session: Session, now: datetime) -> Check:
    bad = {Freshness.stale, Freshness.unavailable}
    problems = [f"{d.dataset}: {d.status.value}" for d in dataset_freshness(session, now)
                if d.status in bad]  # fmt: skip
    return _check("stale_data", problems, "datasets are within their freshness policy")


def scoring(session: Session, now: datetime) -> Check:
    settled = (
        Game.status == GameStatus.final,
        Game.stats_finalized_at.is_not(None),
        Game.stats_finalized_at < now - SCORING_GRACE,
    )
    players = session.scalar(
        select(func.count())
        .select_from(Prediction)
        .join(Game, Game.id == Prediction.game_id)
        .join(
            PlayerGameStats,
            (PlayerGameStats.game_id == Prediction.game_id)
            & (PlayerGameStats.player_id == Prediction.player_id),
        )
        .where(
            *settled,
            Prediction.kind == PredictionKind.pregame,
            PlayerGameStats.minutes > 0,
            ~exists().where(PredictionEvaluation.prediction_id == Prediction.id),
        )
    )
    games = session.scalar(
        select(func.count())
        .select_from(GamePrediction)
        .join(Game, Game.id == GamePrediction.game_id)
        .where(
            *settled,
            ~exists().where(GamePredictionEvaluation.forecast_id == GamePrediction.id),
        )
    )
    problems = []
    if players:
        problems.append(f"{players} player forecasts are unscored")
    if games:
        problems.append(f"{games} game forecasts are unscored")
    return _check("scoring", problems, "finished games are scored")


def event_backlog(session: Session, now: datetime) -> Check:
    count = session.scalar(
        select(func.count())
        .select_from(SyncEvent)
        .where(SyncEvent.processed_at.is_(None), SyncEvent.created_at < now - EVENT_GRACE)
    )
    problems = [f"{count} sync events are waiting"] if count else []
    return _check("event_backlog", problems, "no sync events are waiting")


def model(session: Session, artifacts_dir: Path) -> Check:
    try:
        release = active_release(session, artifacts_dir)
    except (ArtifactMismatch, LookupError, FileNotFoundError) as error:
        return Check("model", "fail", f"active release failed verification: {error}")
    if release is None:
        return Check("model", "fail", "no active release")
    return Check("model", "ok", f"{release.version} verified")


def run_checks(session: Session, now: datetime, artifacts_dir: Path) -> list[Check]:
    return [
        overdue_sync(session, now),
        failed_ingestion(session, now),
        stale_data(session, now),
        scoring(session, now),
        event_backlog(session, now),
        model(session, artifacts_dir),
    ]
