from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.ingestion import jobs
from app.ingestion.client import FetchResult, RetryableSourceError, UnexpectedResponseError
from app.ingestion.writer import upsert
from app.models import (
    FanPost,
    Game,
    GameStatus,
    IngestionRun,
    Player,
    PlayerGameStats,
    PlayerInjury,
    PlayerMatchup,
    RunStatus,
    SyncEvent,
    SyncEventType,
    SyncSchedule,
    Team,
)
from app.sync import worker
from app.sync.freshness import Freshness, dataset_freshness
from tests.fixtures import SEASON, TEAMS, FakeSource, FixtureGame, schedule

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
            .where(
                SyncSchedule.job.in_(
                    ["metadata", "corrections", "careers", "injuries", "attendance", "fan_posts"]
                )
            )
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
        "matchups": "succeeded",
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


def test_a_live_poll_needs_no_source_call_when_no_game_is_on(engine, source):
    assert worker.poll_live_once(engine, source, NOW) is None
    assert not [c for c in source.calls if c["endpoint"] == "ScoreboardV3"]


def test_live_polling_slows_down_when_the_source_fails_or_nothing_is_on():
    assert worker.next_live_wait(0, True) == 5
    assert worker.next_live_wait(0, False) == 30
    assert [worker.next_live_wait(n, True) for n in (1, 2, 5)] == [10, 20, 60]


def test_the_long_careers_job_waits_while_games_are_live(engine, source):
    later = _live_game(engine, source)
    with Session(engine) as s, s.begin():
        s.execute(
            update(SyncSchedule).where(SyncSchedule.job == "careers").values(next_run_at=later)
        )
    assert worker.run_due(engine, source, later)["careers"] == "deferred: games are live"
    assert schedules(engine)["careers"] == later + timedelta(minutes=30)


def test_matchups_job_stores_who_guarded_whom_for_finished_games(engine, source):
    worker.run_due(engine, source, NOW)
    with Session(engine) as s:
        game = s.scalars(select(Game).where(Game.status == GameStatus.final)).first()
        offense, defense = s.scalars(
            select(PlayerGameStats.player_id).where(PlayerGameStats.game_id == game.id)
        ).all()[:2]
        rows = [{
            "teamId": game.home_team_id, "personIdOff": offense, "personIdDef": defense,
            "matchupMinutesSort": 40.0, "partialPossessions": 3.5, "playerPoints": 2,
            "matchupAssists": 0, "matchupTurnovers": 0, "matchupFieldGoalsMade": 1,
            "matchupFieldGoalsAttempted": 1, "matchupThreePointersMade": 0,
            "matchupThreePointersAttempted": 0,
        }]  # fmt: skip
        game_id, away = game.id, game.away_team_id
    source.frames[("BoxScoreMatchupsV3", game_id)] = pd.DataFrame(rows)
    run = jobs.run_job(
        engine, "player_matchups", {"season": SEASON},
        jobs.ingest_player_matchups(source, [game_id]),
    )  # fmt: skip
    assert run.rows_inserted == 1
    with Session(engine) as s:
        stored = s.scalars(select(PlayerMatchup)).one()
        assert (stored.def_team_id, float(stored.partial_possessions)) == (away, 3.5)
        assert game_id not in jobs.games_missing_matchups(s)


def test_matchups_stop_at_once_when_the_source_refuses_and_survive_an_empty_reply(engine, source):
    worker.run_due(engine, source, NOW)
    with Session(engine) as s:
        finals = list(s.scalars(select(Game.id).where(Game.status == GameStatus.final)))
    source.error = RetryableSourceError("ConnectionError")
    repeated = [*finals, *finals, *finals]
    refused = []
    body = jobs.ingest_player_matchups(source, repeated, lambda: refused.append(1))
    run = jobs.run_job(engine, "player_matchups", {"t": 1}, body)
    assert run.rows_rejected == jobs.MATCHUP_FAILURE_LIMIT
    assert refused == [1]
    source.error = None

    class NoTables(FakeSource):
        def fetch(self, endpoint_cls, *, cacheable=False, **params):
            return FetchResult(frames=[], attempts=1)

    run = jobs.run_job(engine, "player_matchups", {"t": 2},
                       jobs.ingest_player_matchups(NoTables(), finals[:1]))  # fmt: skip
    assert (run.status, run.rows_rejected) == (RunStatus.succeeded, 1)


def test_injury_sync_replaces_the_report_and_drops_recovered_players(engine):
    with Session(engine) as s, s.begin():
        upsert(s, Player, [
            {"id": 1, "full_name": "Zed Fixture", "is_active": True, "source_endpoint": "test"},
            {"id": 2, "full_name": "Yan Fixture", "is_active": True, "source_endpoint": "test"},
        ], ["id"])  # fmt: skip

    def report(*names):
        return lambda: {"injuries": [{"injuries": [
            {"status": "Out", "date": "2099-11-03T22:08Z", "athlete": {"displayName": n},
             "details": {"type": "Hip", "returnDate": "2099-11-06"}} for n in names
        ]}]}  # fmt: skip

    jobs.run_job(engine, "injuries", {}, jobs.ingest_injuries(report("Zed Fixture", "Yan Fixture")))
    jobs.run_job(engine, "injuries", {}, jobs.ingest_injuries(report("Yan Fixture")))
    with Session(engine) as s:
        assert list(s.scalars(select(PlayerInjury.player_id))) == [2]
    with pytest.raises(jobs.PartialResponseError):
        jobs.run_job(engine, "injuries", {}, jobs.ingest_injuries(report()))


def test_fan_post_sync_replaces_posts_so_deleted_ones_leave(engine):
    with Session(engine) as s, s.begin():
        upsert(s, Team, [
            {"id": 1, "abbreviation": "AAA", "city": "Testville", "name": "Lakers"},
        ], ["id"])  # fmt: skip
    now = datetime.now(UTC).isoformat()

    def found(*keys):
        posts = [{
            "uri": f"at://did:plc:x/app.bsky.feed.post/{k}",
            "author": {"handle": f"{k}.example.com"},
            "record": {"text": "The Lakers look great on defense this week", "createdAt": now},
            "likeCount": 9,
        } for k in keys]  # fmt: skip
        return lambda query, since: posts

    jobs.run_job(engine, "fan_posts", {}, jobs.ingest_fan_posts(found("a", "b")))
    jobs.run_job(engine, "fan_posts", {}, jobs.ingest_fan_posts(found("b")))
    with Session(engine) as s:
        assert [p.author_handle for p in s.scalars(select(FanPost))] == ["b.example.com"]
    with pytest.raises(jobs.PartialResponseError):
        jobs.run_job(engine, "fan_posts", {}, jobs.ingest_fan_posts(found()))


def test_the_fan_post_job_does_nothing_without_credentials(engine, source, monkeypatch):
    monkeypatch.setattr("app.sync.worker.fan_posts.configured", lambda: False)
    assert worker.job_executions("fan_posts", source, engine, SEASON) == []


def test_matchup_games_with_unusable_replies_are_skipped_without_ending_the_batch(engine, source):
    worker.run_due(engine, source, NOW)
    with Session(engine) as s:
        finals = list(s.scalars(select(Game.id).where(Game.status == GameStatus.final)))
    source.error = UnexpectedResponseError("boxscorematchupsv3: no tables")
    repeated = [*finals, *finals, *finals]
    refused = []
    body = jobs.ingest_player_matchups(source, repeated, lambda: refused.append(1))
    run = jobs.run_job(engine, "player_matchups", {"t": 3}, body)
    assert (run.status, run.rows_rejected) == (RunStatus.succeeded, len(repeated))
    assert refused == []


def test_careers_skip_players_with_empty_replies_and_stop_only_when_refused(engine, source):
    worker.run_due(engine, source, NOW)
    with Session(engine) as s:
        ids = list(s.scalars(select(Player.id)))
    repeated = [*ids, *ids, *ids, *ids, *ids, *ids]
    source.error = UnexpectedResponseError(
        "playercareerstats: response did not match ('resultSet')"
    )
    refused = []
    body = jobs.ingest_player_careers(source, repeated, lambda: refused.append(1))
    run = jobs.run_job(engine, "player_careers", {"t": 1}, body)
    assert (run.status, run.rows_rejected) == (RunStatus.succeeded, len(repeated))
    assert refused == []

    source.error = RetryableSourceError("ConnectionError")
    body = jobs.ingest_player_careers(source, repeated, lambda: refused.append(1))
    run = jobs.run_job(engine, "player_careers", {"t": 2}, body)
    assert run.rows_rejected == jobs.CAREER_FAILURE_LIMIT
    assert refused == [1]
