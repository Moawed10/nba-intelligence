"""Scheduled synchronization (docs/data-synchronization.md).

One worker process runs due jobs from the persisted `sync_schedules` table. Each job execution goes
through `run_job`, whose per-job advisory lock keeps concurrent workers from duplicating work.
"""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, exists, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.ingestion import jobs
from app.ingestion.client import StatsSource
from app.ingestion.transforms import current_season_start_year
from app.models import (
    Game,
    GameStatus,
    IngestionRun,
    Player,
    PlayerGameStats,
    RunStatus,
    SeasonType,
    SyncEvent,
    SyncEventType,
    SyncSchedule,
)
from app.services import game_forecasts, prediction_lifecycle

log = logging.getLogger(__name__)

LEASE = timedelta(minutes=15)
RECENT_GAME_WINDOW = timedelta(hours=36)
CAREER_BATCH = 200
LONGEST_GAME = timedelta(hours=6)
CAREERS_RETRY_DURING_GAMES = timedelta(minutes=30)
LIVE_POLL_SECONDS = 5.0
LIVE_IDLE_SECONDS = 30.0
LIVE_MAX_BACKOFF_SECONDS = 60.0
NOT_FINAL = (GameStatus.scheduled, GameStatus.delayed, GameStatus.in_progress)


@dataclass(frozen=True)
class JobSpec:
    interval: timedelta
    active_interval: timedelta | None = None


JOBS: dict[str, JobSpec] = {
    # Faster while any game is near or past tip-off and not yet final.
    "schedule": JobSpec(
        interval=timedelta(minutes=30),
        active_interval=timedelta(seconds=60),
    ),
    "game_logs": JobSpec(interval=timedelta(hours=6), active_interval=timedelta(minutes=10)),
    "metadata": JobSpec(interval=timedelta(hours=24)),
    "corrections": JobSpec(interval=timedelta(days=7)),
    # Active players' season-by-season careers (one request per player, about ten minutes).
    "careers": JobSpec(interval=timedelta(hours=24)),
    # Scores finished games and refreshes stale forecasts for games in the next 48 hours. It writes
    # no NBA data, so it runs outside ingestion runs and does not advance data_version.
    "predictions": JobSpec(interval=timedelta(minutes=15)),
}


def games_active(session: Session, now: datetime) -> bool:
    """True while some game is between 15 minutes before tip-off and final (capped at 30 hours)."""
    return bool(session.scalar(select(exists().where(
        Game.tipoff_at <= now + timedelta(minutes=15),
        Game.tipoff_at >= now - timedelta(hours=30),
        Game.status.in_(NOT_FINAL),
    ))))  # fmt: skip


def games_live(session: Session, now: datetime) -> bool:
    return bool(session.scalar(select(exists().where(
        Game.tipoff_at <= now + timedelta(minutes=15),
        Game.tipoff_at >= now - LONGEST_GAME,
        Game.status.in_(NOT_FINAL),
    ))))  # fmt: skip


def stats_pending(session: Session, now: datetime) -> bool:
    """True while a recent final game's box score is not yet confirmed stable."""
    return bool(session.scalar(select(exists().where(
        Game.status == GameStatus.final,
        Game.stats_finalized_at.is_(None),
        Game.tipoff_at >= now - RECENT_GAME_WINDOW,
    ))))  # fmt: skip


def next_interval(job: str, session: Session, now: datetime) -> timedelta:
    spec = JOBS[job]
    if spec.active_interval is None:
        return spec.interval
    active = games_active(session, now) or (job == "game_logs" and stats_pending(session, now))
    return spec.active_interval if active else spec.interval


def ensure_schedules(engine: Engine, now: datetime) -> None:
    with Session(engine) as s, s.begin():
        s.execute(
            insert(SyncSchedule)
            .values([{"job": job, "interval_seconds": int(spec.interval.total_seconds()),
                      "next_run_at": now} for job, spec in JOBS.items()])
            .on_conflict_do_nothing(index_elements=["job"])
        )  # fmt: skip


def recover_abandoned(engine: Engine, now: datetime) -> int:
    """Runs still marked running past the lease belonged to a worker that died; mark them."""
    with Session(engine) as s, s.begin():
        result = s.execute(
            update(IngestionRun)
            .where(IngestionRun.status == RunStatus.running,
                   func.coalesce(IngestionRun.heartbeat_at, IngestionRun.started_at) < now - LEASE)
            .values(status=RunStatus.abandoned, finished_at=now,
                    error="Worker stopped before the run finished")
        )  # fmt: skip
        return result.rowcount or 0


def due_jobs(engine: Engine, now: datetime) -> list[str]:
    with Session(engine) as s:
        return list(s.scalars(
            select(SyncSchedule.job)
            .where(SyncSchedule.enabled, SyncSchedule.next_run_at <= now)
            .order_by(SyncSchedule.next_run_at)
        ))  # fmt: skip


Execution = tuple[str, dict[str, Any], Callable[[jobs.RunContext], None]]


def _season_types(engine: Engine, season: int) -> list[SeasonType]:
    with Session(engine) as s:
        stmt = select(Game.season_type).where(Game.season_id == season).distinct()
        present = set(s.scalars(stmt))
    return [t for t in SeasonType if t in present] or [SeasonType.regular]


def job_executions(job: str, client: StatsSource, engine: Engine, season: int) -> list[Execution]:
    if job == "schedule":
        return [("schedule", {"season": season}, jobs.ingest_schedule(client, season))]
    if job in ("game_logs", "corrections"):
        return [
            ("game_logs", {"season": season, "season_type": st.value},
             jobs.ingest_game_logs(client, season, st))
            for st in _season_types(engine, season)
        ]  # fmt: skip
    if job == "metadata":
        return [
            ("teams", {"season": season}, jobs.ingest_teams(client, season)),
            ("players", {"season": season}, jobs.ingest_players(client, season)),
        ]
    if job == "careers":
        with Session(engine) as s:
            active = list(s.scalars(select(Player.id).where(Player.is_active).order_by(Player.id)))
        return [
            ("player_careers", {"first": batch[0], "count": len(batch)},
             jobs.ingest_player_careers(client, batch))
            for batch in (active[i : i + CAREER_BATCH] for i in range(0, len(active), CAREER_BATCH))
        ]  # fmt: skip
    raise KeyError(job)


def finalize_stable_box_scores(engine: Engine, run_started: datetime, now: datetime) -> int:
    """A final game whose player lines predate this run and were left unchanged by it is stable.

    Only recently played games emit GAME_STATS_FINALIZED; older games (e.g. a historical backfill)
    are marked stable silently, so evaluation is not triggered for seasons-old results.
    """
    with Session(engine) as s, s.begin():
        latest_line = (
            select(func.max(PlayerGameStats.updated_at))
            .where(PlayerGameStats.game_id == Game.id)
            .scalar_subquery()
        )
        rows = s.execute(
            select(Game.id, Game.tipoff_at).where(
                Game.status == GameStatus.final,
                Game.stats_finalized_at.is_(None),
                latest_line < run_started,
            )
        ).all()  # fmt: skip
        if not rows:
            return 0
        s.execute(
            update(Game).where(Game.id.in_([r.id for r in rows])).values(stats_finalized_at=now)
        )
        recent = [r.id for r in rows if r.tipoff_at and r.tipoff_at >= now - RECENT_GAME_WINDOW]
        for gid in recent:
            jobs.emit_event(s, SyncEventType.GAME_STATS_FINALIZED, f"GAME_STATS_FINALIZED:{gid}",
                            {"game_id": gid}, None)  # fmt: skip
        return len(rows)


EventHandler = Callable[[Session, SyncEvent], None]


def _score_finalized(session: Session, event: SyncEvent) -> None:
    prediction_lifecycle.score_game(session, event.payload["game_id"], datetime.now(UTC))


# Caches need no handler: every committed run advances data_version, part of every cache key.
HANDLERS: dict[SyncEventType, EventHandler] = {
    SyncEventType.GAME_STATS_FINALIZED: _score_finalized,
}


def maintain_predictions(
    engine: Engine, now: datetime, artifacts_dir: Path
) -> dict[str, int] | None:
    """Score pending finals, refresh stale player forecasts and store score forecasts for the
    next 48 hours of games. None when another worker holds it."""
    key = func.hashtextextended("predictions", 0)
    # The lock belongs to one database connection, so the session is pinned to it: commits and
    # rollbacks inside the job must not hand it back to the pool before the unlock.
    with engine.connect() as conn:
        if not conn.scalar(select(func.pg_try_advisory_lock(key))):
            conn.rollback()
            return None
        conn.commit()
        try:
            with Session(bind=conn) as s:
                scored = prediction_lifecycle.score_pending(s, now)
                s.commit()
                counts = prediction_lifecycle.refresh_due(s, artifacts_dir, now)
                s.commit()
                games = game_forecasts.store_upcoming(s, artifacts_dir, now)
                s.commit()
                return {"scored": scored, **counts, **games}
        finally:
            conn.rollback()
            conn.execute(select(func.pg_advisory_unlock(key)))
            conn.commit()


def drain_events(engine: Engine, now: datetime, batch: int = 500) -> int:
    total = 0
    while (handled := _drain_batch(engine, now, batch)) > 0:
        total += handled
    return total


def _drain_batch(engine: Engine, now: datetime, limit: int) -> int:
    with Session(engine) as s, s.begin():
        events = s.scalars(
            select(SyncEvent).where(SyncEvent.processed_at.is_(None)).order_by(SyncEvent.id)
            .limit(limit).with_for_update(skip_locked=True)
        ).all()  # fmt: skip
        for event in events:
            handler = HANDLERS.get(event.type)
            if handler:
                handler(s, event)
            event.processed_at = now
        return len(events)


def run_due(engine: Engine, client: StatsSource, now: datetime | None = None) -> dict[str, str]:
    """Runs every due job once and reschedules it. Returns job -> outcome."""
    now = now or datetime.now(UTC)
    ensure_schedules(engine, now)
    recover_abandoned(engine, now)
    season = current_season_start_year(now)
    outcomes: dict[str, str] = {}
    for job in due_jobs(engine, now):
        if job == "careers":
            with Session(engine) as s, s.begin():
                if games_live(s, now):
                    s.execute(update(SyncSchedule).where(SyncSchedule.job == job)
                              .values(next_run_at=now + CAREERS_RETRY_DURING_GAMES))  # fmt: skip
                    outcomes[job] = "deferred: games are live"
                    continue
        started = datetime.now(UTC)
        outcome = "succeeded"
        if job == "predictions":
            try:
                result = maintain_predictions(engine, now, get_settings().artifacts_dir)
                if result is None:
                    outcome = "skipped: running elsewhere"
                else:
                    log.info("predictions maintained", extra=result)
            except Exception:
                log.exception("prediction maintenance failed")
                outcome = "failed"
        for name, params, body in ([] if job == "predictions" else
                                   job_executions(job, client, engine, season)):  # fmt: skip
            try:
                if jobs.run_job(engine, name, params, body) is None:
                    outcome = "skipped: running elsewhere"
            except Exception:
                outcome = "failed"
        if job in ("game_logs", "corrections") and outcome == "succeeded":
            finalize_stable_box_scores(engine, started, now)
        with Session(engine) as s, s.begin():
            interval = next_interval(job, s, now)
            s.execute(update(SyncSchedule).where(SyncSchedule.job == job)
                      .values(next_run_at=now + interval))  # fmt: skip
        outcomes[job] = outcome
    drain_events(engine, datetime.now(UTC))
    return outcomes


def live_game_dates(session: Session, now: datetime) -> list[date]:
    return list(session.scalars(select(Game.game_date).where(
        Game.tipoff_at <= now + timedelta(minutes=15),
        Game.tipoff_at >= now - LONGEST_GAME,
        Game.status.in_(NOT_FINAL),
    ).distinct()))  # fmt: skip


def poll_live_once(engine: Engine, client: StatsSource, now: datetime) -> int | None:
    with Session(engine) as s:
        dates = live_game_dates(s, now)
    if not dates:
        return None
    return jobs.poll_live_scores(engine, client, dates, now)


def next_live_wait(failures: int, active: bool) -> float:
    if failures:
        return min(LIVE_POLL_SECONDS * 2.0**failures, LIVE_MAX_BACKOFF_SECONDS)
    return LIVE_POLL_SECONDS if active else LIVE_IDLE_SECONDS


def run_live_scores(engine: Engine, client: StatsSource) -> None:
    failures = 0
    while True:
        active = False
        try:
            active = poll_live_once(engine, client, datetime.now(UTC)) is not None
            failures = 0
        except Exception as error:
            failures += 1
            log.warning("live score poll failed", extra={"error": type(error).__name__})
        time.sleep(next_live_wait(failures, active))


def run_forever(
    engine: Engine, client: StatsSource, live_client: StatsSource, max_sleep: float = 30.0
) -> None:
    log.info("sync worker started", extra={"jobs": list(JOBS)})
    threading.Thread(target=run_live_scores, args=(engine, live_client), daemon=True).start()
    while True:
        outcomes = run_due(engine, client)
        if outcomes:
            log.info("sync jobs ran", extra={"outcomes": outcomes})
        with Session(engine) as s:
            nxt = s.scalar(select(func.min(SyncSchedule.next_run_at)).where(SyncSchedule.enabled))
        wait = max_sleep if nxt is None else (nxt - datetime.now(UTC)).total_seconds()
        time.sleep(min(max_sleep, max(1.0, wait)))
