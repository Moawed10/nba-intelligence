from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.ingestion.writer import upsert
from app.models import (
    Game,
    IngestionRun,
    RunStatus,
    SyncEvent,
    SyncEventType,
    SyncSchedule,
    Team,
)
from app.sync import worker
from app.sync.freshness import Freshness, dataset_freshness
from tests.fixtures import TEAMS, FakeSource, FixtureGame, schedule

pytestmark = pytest.mark.integration

NOW = datetime(2099, 11, 10, 6, tzinfo=UTC)
# Games from the last 36 hours, so their box scores are still awaiting confirmation.
GAMES = [FixtureGame(1, "2099-11-09", home=1, away=2), FixtureGame(2, "2099-11-10", home=3, away=1)]


@pytest.fixture
def source(engine) -> FakeSource:
    with Session(engine) as s, s.begin():
        upsert(s, Team, TEAMS, ["id"])
    src = FakeSource()
    src.set_logs(GAMES)
    src.frames[("ScheduleLeagueV2", None)] = schedule(GAMES)
    worker.ensure_schedules(engine, NOW)
    with Session(engine) as s, s.begin():
        s.execute(
            update(SyncSchedule)
            .where(SyncSchedule.job.in_(["metadata", "corrections", "careers"]))
            .values(next_run_at=NOW + timedelta(days=365))
        )
    return src


def schedules(engine) -> dict[str, datetime]:
    with Session(engine) as s:
        return dict(s.execute(select(SyncSchedule.job, SyncSchedule.next_run_at)).all())


def test_due_jobs_run_once_and_are_rescheduled(engine, source):
    assert worker.run_due(engine, source, NOW) == {
        "schedule": "succeeded",
        "game_logs": "succeeded",
        "predictions": "succeeded",
    }
    nxt = schedules(engine)
    assert nxt["schedule"] == NOW + timedelta(minutes=30)
    assert nxt["predictions"] == NOW + timedelta(minutes=15)
    assert nxt["game_logs"] == NOW + timedelta(minutes=10), "unfinalized box scores keep polling"

    # A restarted worker at the same instant finds nothing due: schedules are persisted.
    assert worker.run_due(engine, source, NOW) == {}
    later = NOW + timedelta(minutes=31)
    assert worker.run_due(engine, source, later) == {
        "schedule": "succeeded",
        "game_logs": "succeeded",
        "predictions": "succeeded",
    }


def test_polling_speeds_up_only_while_games_are_live(engine, source):
    with Session(engine) as s:
        assert worker.next_interval("schedule", s, NOW) == timedelta(minutes=30)
    upcoming = [FixtureGame(5, "2099-11-10", home=1, away=3)]
    worker.run_due(
        engine,
        FakeSource(
            frames={
                **source.frames,
                ("ScheduleLeagueV2", None): schedule(upcoming, status=1, tipoff_hour=6),
            }
        ),
        NOW,
    )
    with Session(engine) as s:
        # Tip-off is 06:30; the live window opens 15 minutes before.
        assert worker.next_interval("schedule", s, NOW + timedelta(minutes=20)) == timedelta(
            seconds=5
        )
        assert worker.next_interval("schedule", s, NOW + timedelta(hours=8)) == timedelta(
            seconds=60
        )
        assert worker.next_interval("schedule", s, NOW + timedelta(days=2)) == timedelta(minutes=30)


def test_box_scores_finalize_after_an_unchanged_refetch(engine, source):
    worker.run_due(engine, source, NOW)
    with Session(engine) as s:
        assert set(s.scalars(select(Game.stats_finalized_at))) == {None}

    worker.run_due(engine, source, NOW + timedelta(minutes=31))
    with Session(engine) as s:
        assert None not in set(s.scalars(select(Game.stats_finalized_at)))
        finalized = s.scalars(
            select(SyncEvent).where(SyncEvent.type == SyncEventType.GAME_STATS_FINALIZED)
        ).all()
        unprocessed = s.scalars(select(SyncEvent).where(SyncEvent.processed_at.is_(None))).all()
    assert len(finalized) == 2
    assert unprocessed == []
    with Session(engine) as s:
        assert worker.next_interval("game_logs", s, NOW) == timedelta(hours=6)


def test_historical_games_finalize_without_events(engine, source):
    old = [FixtureGame(7, "2099-10-01", home=2, away=3)]
    source.set_logs([*GAMES, *old])
    source.frames[("ScheduleLeagueV2", None)] = schedule([*GAMES, *old])
    worker.run_due(engine, source, NOW)
    worker.run_due(engine, source, NOW + timedelta(minutes=31))
    with Session(engine) as s:
        assert s.get(Game, old[0].id).stats_finalized_at is not None
        keys = s.scalars(
            select(SyncEvent.dedupe_key).where(SyncEvent.type == SyncEventType.GAME_STATS_FINALIZED)
        ).all()
    assert sorted(keys) == sorted(f"GAME_STATS_FINALIZED:{g.id}" for g in GAMES)


def test_event_outbox_drains_completely(engine, source):
    from app.ingestion.jobs import emit_event

    with Session(engine) as s, s.begin():
        for i in range(1203):
            emit_event(s, SyncEventType.PLAYER_STATS_UPDATED, f"TEST:{i}", {}, None)
    assert worker.drain_events(engine, NOW, batch=500) == 1203
    with Session(engine) as s:
        assert s.scalars(select(SyncEvent).where(SyncEvent.processed_at.is_(None))).all() == []


def test_abandoned_runs_are_recovered(engine, source):
    with Session(engine) as s, s.begin():
        s.add(
            IngestionRun(
                job="game_logs",
                params={},
                status=RunStatus.running,
                started_at=NOW - timedelta(hours=1),
                heartbeat_at=NOW - timedelta(hours=1),
            )
        )
        s.add(
            IngestionRun(
                job="schedule",
                params={},
                status=RunStatus.running,
                started_at=NOW - timedelta(minutes=1),
                heartbeat_at=NOW - timedelta(minutes=1),
            )
        )
    assert worker.recover_abandoned(engine, NOW) == 1
    with Session(engine) as s:
        statuses = s.scalars(select(IngestionRun.status).order_by(IngestionRun.id)).all()
    assert statuses == [RunStatus.abandoned, RunStatus.running]


def test_failed_job_is_recorded_and_retried_next_cycle(engine, source):
    source.error = ConnectionError("simulated outage")
    assert worker.run_due(engine, source, NOW)["schedule"] == "failed"
    source.error = None
    assert worker.run_due(engine, source, NOW + timedelta(minutes=31))["schedule"] == "succeeded"


def test_freshness_reflects_runs(engine, source):
    with Session(engine) as s:
        before = {d.dataset: d.status for d in dataset_freshness(s, NOW)}
    assert before["schedule"] == Freshness.unavailable

    worker.run_due(engine, source, NOW)
    with Session(engine) as s:
        rows = {d.dataset: d for d in dataset_freshness(s, datetime.now(UTC))}
    assert rows["schedule"].status == Freshness.fresh
    assert rows["final_box_scores"].coverage_end.isoformat() == "2099-11-10"
    with Session(engine) as s:
        aged = {
            d.dataset: d.status
            for d in dataset_freshness(s, datetime.now(UTC) + timedelta(hours=3))
        }
    assert aged["schedule"] == Freshness.stale
    assert aged["final_box_scores"] == Freshness.fresh


def _live_game(engine, source) -> datetime:
    upcoming = [FixtureGame(5, "2099-11-10", home=1, away=3)]
    source.frames[("ScheduleLeagueV2", None)] = schedule(upcoming, status=2, tipoff_hour=6)
    worker.run_due(engine, source, NOW)
    return NOW + timedelta(hours=1)


def test_a_failed_fetch_during_a_game_waits_a_minute_instead_of_5_seconds(engine, source):
    later = _live_game(engine, source)
    source.error = RuntimeError("source refused the request")
    outcomes = worker.run_due(engine, source, later)
    assert outcomes["schedule"] == "failed"
    assert schedules(engine)["schedule"] == later + timedelta(seconds=60)


def test_the_long_careers_job_waits_while_games_are_live(engine, source):
    later = _live_game(engine, source)
    with Session(engine) as s, s.begin():
        s.execute(
            update(SyncSchedule).where(SyncSchedule.job == "careers").values(next_run_at=later)
        )
    assert worker.run_due(engine, source, later)["careers"] == "deferred: games are live"
    assert schedules(engine)["careers"] == later + timedelta(minutes=30)
