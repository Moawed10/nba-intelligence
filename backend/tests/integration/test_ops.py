from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ingestion import jobs
from app.ml import inference
from app.models import IngestionRun, ReleaseStatus, RunStatus, SyncEventType, SyncSchedule
from app.ops import event_backlog, failed_ingestion, model, overdue_sync, run_checks, scoring
from app.services.prediction_lifecycle import score_pending
from tests.api.conftest import NOW
from tests.api.test_predictions import (  # noqa: F401
    NEXT_GAME,
    STAR,
    _release,
    client,
    league,
    serving,
)

pytestmark = pytest.mark.integration


def test_overdue_jobs_and_a_worker_that_never_ran_fail(league):  # noqa: F811
    with Session(league) as s, s.begin():
        assert overdue_sync(s, NOW).status == "fail"
        s.add(
            SyncSchedule(job="schedule", interval_seconds=60, next_run_at=NOW - timedelta(hours=1))
        )
    with Session(league) as s:
        result = overdue_sync(s, NOW)
        assert result.status == "fail" and "schedule" in result.detail
        assert overdue_sync(s, NOW - timedelta(hours=1)).status == "ok"


def test_a_job_failure_clears_only_when_the_same_job_succeeds_later(league):  # noqa: F811
    params = {"season": 2099}
    with Session(league) as s, s.begin():
        s.add(IngestionRun(job="schedule", params=params, status=RunStatus.failed,
                           started_at=NOW - timedelta(hours=2)))  # fmt: skip
    with Session(league) as s:
        assert failed_ingestion(s, NOW).status == "fail"
    with Session(league) as s, s.begin():
        s.add(IngestionRun(job="schedule", params=params, status=RunStatus.succeeded,
                           started_at=NOW - timedelta(hours=1)))  # fmt: skip
    with Session(league) as s:
        assert failed_ingestion(s, NOW).status == "ok"


def test_unscored_finished_games_fail_and_scoring_clears_them(serving, league):  # noqa: F811
    response = serving.post(
        "/api/v1/predictions", json={"player_id": STAR, "game_id": NEXT_GAME.id}
    )
    assert response.status_code == 201
    with league.begin() as conn:
        conn.execute(
            text(
                "UPDATE games SET status = 'final', home_score = 100, away_score = 90, "
                "stats_finalized_at = :at WHERE id = :g"
            ),
            {"at": NOW - timedelta(hours=2), "g": NEXT_GAME.id},
        )
        conn.execute(
            text(
                "INSERT INTO player_game_stats (game_id, player_id, team_id, minutes, fgm, fga, "
                "fg3m, fg3a, ftm, fta, oreb, dreb, reb, ast, stl, blk, tov, pf, pts, plus_minus, "
                "source_endpoint) VALUES (:g, :p, 1, 40, 5, 10, 0, 0, 0, 0, 0, 3, 3, 2, 1, 0, 1, "
                "2, 10, 0, 'fixture')"
            ),
            {"g": NEXT_GAME.id, "p": STAR},
        )
    with Session(league) as s, s.begin():
        assert "player forecasts" in scoring(s, NOW).detail
        score_pending(s, NOW)
    with Session(league) as s:
        assert scoring(s, NOW).status == "ok"


def test_a_player_who_did_not_play_does_not_trigger_rescoring_on_every_run(serving, league):  # noqa: F811
    assert (
        serving.post(
            "/api/v1/predictions", json={"player_id": STAR, "game_id": NEXT_GAME.id}
        ).status_code
        == 201
    )
    with league.begin() as conn:
        conn.execute(
            text(
                "UPDATE games SET status = 'final', home_score = 100, away_score = 90, "
                "stats_finalized_at = :at WHERE id = :g"
            ),
            {"at": NOW - timedelta(hours=2), "g": NEXT_GAME.id},
        )
    with Session(league) as s, s.begin():
        assert score_pending(s, NOW) == 0
        assert scoring(s, NOW).status == "ok"


def test_events_left_waiting_fail(league):  # noqa: F811
    with Session(league) as s, s.begin():
        s.execute(text("UPDATE sync_events SET processed_at = now()"))
        jobs.emit_event(s, SyncEventType.GAME_STATS_FINALIZED, "stuck", {"game_id": "x"}, None)
    with Session(league) as s:
        assert event_backlog(s, NOW).status == "fail"


def test_model_check_names_each_bad_state(league, tmp_path):  # noqa: F811
    inference.clear_cache()
    with Session(league) as s:
        assert "no active release" in model(s, tmp_path).detail
    _release(league, tmp_path, "2099.11.10-1", ReleaseStatus.active)
    inference.clear_cache()
    with Session(league) as s:
        assert model(s, tmp_path).status == "ok"
    inference.clear_cache()
    sorted(tmp_path.rglob("*.joblib"))[0].unlink()
    with Session(league) as s:
        assert "failed verification" in model(s, tmp_path).detail
    inference.clear_cache()


def test_readiness_reports_the_model_state(serving, tmp_path):  # noqa: F811
    inference.clear_cache()
    assert serving.get("/api/v1/readiness").json()["checks"]["model"] == "ok"
    inference.clear_cache()
    sorted(tmp_path.rglob("*.joblib"))[0].unlink()
    body = serving.get("/api/v1/readiness").json()
    assert body["status"] == "ready" and body["checks"]["model"] == "failed_verification"
    inference.clear_cache()


def test_all_checks_run_together(league, tmp_path):  # noqa: F811
    with Session(league) as s:
        names = [c.name for c in run_checks(s, NOW, tmp_path)]
    assert names == ["overdue_sync", "failed_ingestion", "stale_data", "scoring",
                     "event_backlog", "model"]  # fmt: skip
