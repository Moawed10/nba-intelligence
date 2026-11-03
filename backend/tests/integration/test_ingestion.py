import json
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db import current_data_version
from app.ingestion import jobs
from app.ingestion.client import RetryableSourceError
from app.ingestion.integrity import integrity_report
from app.ingestion.writer import upsert
from app.models import (
    Game,
    GameStatus,
    IngestionRun,
    Player,
    PlayerGameStats,
    RunStatus,
    SeasonType,
    SourceCorrection,
    SyncEvent,
    SyncEventType,
    Team,
    TeamGameStats,
)
from tests.fixtures import SEASON, TEAMS, FakeSource, FixtureGame, schedule, scoreboard

pytestmark = pytest.mark.integration

GAMES = [
    FixtureGame(1, "2099-11-01", home=1, away=2),
    FixtureGame(2, "2099-11-03", home=3, away=1),
    FixtureGame(3, "2099-11-05", home=2, away=3, neutral=True),
]
LOG_PARAMS = {"season": SEASON, "season_type": "regular"}


def counts(engine) -> dict[str, int]:
    with Session(engine) as s:
        return {
            m.__tablename__: s.scalar(select(func.count()).select_from(m))
            for m in (Game, TeamGameStats, PlayerGameStats, Player)
        }


def run_logs(engine, source):
    return jobs.run_job(
        engine, "game_logs", LOG_PARAMS, jobs.ingest_game_logs(source, SEASON, SeasonType.regular)
    )


def run_schedule(engine, source, frame=None):
    if frame is not None:
        source.frames[("ScheduleLeagueV2", None)] = frame
    return jobs.run_job(
        engine, "schedule", {"season": SEASON}, jobs.ingest_schedule(source, SEASON)
    )


@pytest.fixture
def source(engine) -> FakeSource:
    with Session(engine) as s, s.begin():
        upsert(s, Team, TEAMS, ["id"])
    src = FakeSource()
    src.set_logs(GAMES)
    src.frames[("ScheduleLeagueV2", None)] = schedule(GAMES)
    return src


def test_repeated_ingestion_creates_no_duplicates(engine, source):
    assert run_schedule(engine, source).status == RunStatus.succeeded
    assert run_logs(engine, source).rows_rejected == 0
    after_first = counts(engine)
    assert after_first == {"games": 3, "team_game_stats": 6, "player_game_stats": 30, "players": 15}

    for _ in range(2):
        again = run_logs(engine, source)
        assert (again.rows_inserted, again.rows_updated) == (0, 0)
        assert run_schedule(engine, source).rows_updated == 0
    assert counts(engine) == after_first

    with Session(engine) as s:
        report = integrity_report(s)
    assert all(v == 0 for v in report["checks"].values()), report["checks"]
    assert report["coverage"][0]["completeness"] == 1.0


def test_neutral_site_game_uses_schedule_home(engine, source):
    run_schedule(engine, source)
    run_logs(engine, source)
    with Session(engine) as s:
        game = s.get(Game, GAMES[2].id)
    assert (game.home_team_id, game.away_team_id, game.home_score) == (2, 3, 55)


def test_correction_is_detected_logged_and_applied(engine, source):
    run_schedule(engine, source)
    run_logs(engine, source)
    source.set_logs(GAMES, {(GAMES[0].id, 100): {"AST": 7}})
    run = run_logs(engine, source)
    assert (run.rows_inserted, run.rows_updated) == (0, 1)
    with Session(engine) as s:
        line = s.get(PlayerGameStats, (GAMES[0].id, 100))
        logged = s.scalars(select(SourceCorrection)).all()
        events = s.scalars(select(SyncEvent.type)).all()
    assert line.ast == 7 and line.ingestion_run_id == run.id
    assert [(c.column_name, c.old_value, c.new_value) for c in logged] == [("ast", "2", "7")]
    assert SyncEventType.HISTORICAL_DATA_CORRECTED in events


def test_partial_response_fails_without_writing(engine, source):
    run_schedule(engine, source)
    run_logs(engine, source)
    before = counts(engine)
    source.set_logs(GAMES[:1])
    with pytest.raises(jobs.PartialResponseError):
        run_logs(engine, source)
    assert counts(engine) == before
    with Session(engine) as s:
        failed = s.scalars(
            select(IngestionRun).where(IngestionRun.status == RunStatus.failed)
        ).one()
        event = s.scalars(
            select(SyncEvent).where(SyncEvent.type == SyncEventType.INGESTION_FAILED)
        ).one()
    assert "PartialResponseError" in failed.error
    assert event.ingestion_run_id == failed.id


def test_source_failure_preserves_committed_data(engine, source):
    run_schedule(engine, source)
    run_logs(engine, source)
    before = counts(engine)
    source.error = RetryableSourceError("HTTP 503")
    with pytest.raises(RetryableSourceError):
        run_logs(engine, source)
    assert counts(engine) == before


def test_failure_mid_transaction_rolls_back(engine, source):
    run_schedule(engine, source)

    def body(ctx):
        jobs.ingest_game_logs(source, SEASON, SeasonType.regular)(ctx)
        raise RuntimeError("simulated crash after writes")

    with pytest.raises(RuntimeError):
        jobs.run_job(engine, "game_logs", LOG_PARAMS, body)
    assert counts(engine)["player_game_stats"] == 0


def test_same_job_cannot_run_concurrently(engine, source):
    lock_key = f"game_logs:{json.dumps(LOG_PARAMS, sort_keys=True)}"
    with engine.connect() as holder:
        holder.execute(text("SELECT pg_advisory_lock(hashtextextended(:k, 0))"), {"k": lock_key})
        assert run_logs(engine, source) is None
        holder.execute(text("SELECT pg_advisory_unlock(hashtextextended(:k, 0))"), {"k": lock_key})
    assert counts(engine)["player_game_stats"] == 0
    assert run_logs(engine, source).status == RunStatus.succeeded


def test_every_execution_records_its_status(engine, source):
    run_schedule(engine, source)
    run_logs(engine, source)
    source.error = RetryableSourceError("HTTP 503")
    with pytest.raises(RetryableSourceError):
        run_logs(engine, source)
    with Session(engine) as s:
        statuses = s.scalars(select(IngestionRun.status).order_by(IngestionRun.id)).all()
        unfinished = s.scalar(
            select(func.count()).select_from(IngestionRun).where(IngestionRun.finished_at.is_(None))
        )
    assert statuses == [RunStatus.succeeded, RunStatus.succeeded, RunStatus.failed]
    assert unfinished == 0


def test_schedule_lifecycle_events_and_no_downgrade(engine, source):
    run_schedule(engine, source, schedule(GAMES, status=1))
    run_schedule(engine, source, schedule(GAMES, status=2))
    run_logs(engine, source)

    stale = run_schedule(engine, source, schedule(GAMES, status=1))
    assert stale.rows_rejected == 3
    with Session(engine) as s:
        statuses = set(s.scalars(select(Game.status)))
        events = s.scalars(select(SyncEvent.type)).all()
        scores = s.scalars(select(Game.home_score)).all()
    assert statuses == {GameStatus.final}
    assert events.count(SyncEventType.GAME_STARTED) == 3
    assert events.count(SyncEventType.GAME_COMPLETED) == 3
    assert None not in scores


def _with_scores(frame, home, away, text="Q3 5:12"):
    return frame.assign(homeTeam_score=home, awayTeam_score=away, gameStatusText=text)


LIVE_NOW = datetime(2099, 11, 10, 2, tzinfo=UTC)


def _poll(engine, source, status, text, home, away, now=LIVE_NOW):
    source.live_frames = scoreboard(GAMES, status, text, home, away)
    return jobs.poll_live_scores(engine, source, [date.fromisoformat(GAMES[0].date)], now)


def test_live_scores_follow_the_scoreboard_and_the_box_score_has_the_last_word(engine, source):
    run_schedule(engine, source, schedule(GAMES, status=1))
    assert _poll(engine, source, 1, "7:30 pm ET", 0, 0) == 0
    with Session(engine) as s:
        assert set(s.scalars(select(Game.home_score))) == {None}

    assert _poll(engine, source, 2, "Q3 5:12", 61, 58) == len(GAMES)
    with Session(engine) as s:
        game = s.get(Game, GAMES[0].id)
        assert game.status == GameStatus.in_progress
        assert (game.home_score, game.away_score) == (61, 58)
        assert game.provider_status["gameStatusText"] == "Q3 5:12"
        assert game.status_observed_at == LIVE_NOW
        started = s.scalars(select(SyncEvent.type)).all()
    assert started.count(SyncEventType.GAME_STARTED) == len(GAMES)

    assert _poll(engine, source, 2, "Q3 5:12", 61, 58) == 0, (
        "an unchanged scoreboard writes nothing"
    )
    assert _poll(engine, source, 3, "Final", 101, 99) == len(GAMES)
    with Session(engine) as s:
        game = s.get(Game, GAMES[0].id)
        assert (game.status, game.home_score, game.away_score) == (GameStatus.final, 101, 99)

    run_logs(engine, source)
    with Session(engine) as s:
        game = s.get(Game, GAMES[0].id)
        assert (game.home_score, game.away_score) == (55, 55)
        assert s.scalar(select(func.count()).select_from(SourceCorrection)) == 0


def test_live_scoring_does_not_advance_the_data_version(engine, source):
    run_schedule(engine, source, schedule(GAMES, status=1))
    with Session(engine) as s:
        before = current_data_version(s)
    _poll(engine, source, 2, "Q1 11:00", 2, 0)
    with Session(engine) as s:
        assert current_data_version(s) == before


def test_a_slow_schedule_response_cannot_undo_a_newer_live_score(engine, source):
    run_schedule(engine, source, schedule(GAMES, status=1))
    _poll(engine, source, 2, "Q4 1:00", 90, 88)
    run_schedule(engine, source, _with_scores(schedule(GAMES, status=2), 40, 41, "Q2 6:00"))
    with Session(engine) as s:
        game = s.get(Game, GAMES[0].id)
        assert (game.home_score, game.away_score) == (90, 88)
        assert game.provider_status["gameStatusText"] == "Q4 1:00"


def test_a_late_score_never_overwrites_a_finished_game(engine, source):
    run_schedule(engine, source, schedule(GAMES, status=1))
    run_schedule(engine, source, schedule(GAMES, status=2))
    run_logs(engine, source)
    run_schedule(engine, source, _with_scores(schedule(GAMES, status=3), 1, 2, "Final"))
    stale = run_schedule(engine, source, _with_scores(schedule(GAMES, status=2), 3, 4))
    assert stale.rows_rejected == len(GAMES)
    assert _poll(engine, source, 2, "Q2 1:00", 5, 6) == 0
    with Session(engine) as s:
        assert set(s.scalars(select(Game.home_score))) == {55}


def test_tipoff_change_emits_one_schedule_update(engine, source):
    run_schedule(engine, source, schedule(GAMES[:1], status=1, tipoff_hour=0))
    run_schedule(engine, source, schedule(GAMES[:1], status=1, tipoff_hour=2))
    run_schedule(engine, source, schedule(GAMES[:1], status=1, tipoff_hour=2))
    with Session(engine) as s:
        events = s.scalars(
            select(SyncEvent).where(SyncEvent.type == SyncEventType.GAME_SCHEDULE_UPDATED)
        ).all()
    assert len(events) == 1
    assert events[0].payload["tipoff_at"].startswith("2099-11-01T02:30")
