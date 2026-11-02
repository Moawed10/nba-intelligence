"""Game score forecasts against the synthetic league, with a 10-game rolling baseline for points
(so the expected score is each team's recent average) and a fixed logistic margin calibrator."""

import uuid
from datetime import datetime, timedelta

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sklearn.linear_model import LogisticRegression
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from app.ingestion import jobs
from app.ml.artifacts import save_artifact
from app.ml.models import RollingBaseline
from app.ml.team_model import TEAM_FEATURES
from app.models import (
    Algorithm,
    GamePrediction,
    ModelRelease,
    ModelTarget,
    ModelVersion,
    SyncEventType,
)
from app.services import game_forecasts, prediction_lifecycle
from app.sync.worker import drain_events, maintain_predictions
from tests.api.conftest import FINAL, NOW, SCHEDULED, STAR
from tests.api.test_predictions import CONFORMAL, EXTRA, client, league, serving  # noqa: F401

pytestmark = pytest.mark.integration

NEXT_GAME = SCHEDULED[0]  # 2099-11-11, team 1 hosts team 2
LATER_GAME = SCHEDULED[2]  # 2099-11-25, team 1 hosts team 3
URL = "/api/v1/predictions/games"
VERSION = "2099.11.10-1"


@pytest.fixture(autouse=True)
def _small_league(monkeypatch):
    """The fixture league has a handful of games per team, below the production minimum."""
    monkeypatch.setattr(game_forecasts, "MIN_PRIOR_GAMES", 3)


def _add_game_models(engine: Engine, directory) -> None:
    calibrator = LogisticRegression().fit(np.array([[-10.0], [-2.0], [2.0], [10.0]]), [0, 0, 1, 1])
    with Session(engine) as s, s.begin():
        release = s.scalars(select(ModelRelease)).one()
        for target, model, algorithm, conformal in (
            ("team_pts", RollingBaseline("pts"), Algorithm.rolling_baseline, CONFORMAL.to_dict()),
            ("home_win", calibrator, Algorithm.logistic, None),
        ):
            path = f"{release.version}/{target}.joblib"
            digest = save_artifact(directory / path, model, target=target, conformal=conformal)
            s.add(
                ModelVersion(
                    release_id=release.id,
                    target=ModelTarget(target),
                    algorithm=algorithm,
                    is_selected=True,
                    hyperparameters={"fit": "production"},
                    features=list(TEAM_FEATURES),
                    interval_calibration=conformal,
                    artifact_path=path,
                    artifact_sha256=digest,
                    random_seed=0,
                )
            )


@pytest.fixture
def scoring(league: Engine, tmp_path, serving: TestClient) -> TestClient:  # noqa: F811
    _add_game_models(league, tmp_path)
    return serving


def _team_points(engine: Engine, team: int) -> list[float]:
    with engine.connect() as conn:
        return conn.scalars(
            text(
                "SELECT t.pts FROM team_game_stats t JOIN games g ON g.id = t.game_id "
                "WHERE t.team_id = :t AND g.status = 'final' ORDER BY g.game_date"
            ),
            {"t": team},
        ).all()


def test_release_without_a_game_model_is_a_named_503(serving):  # noqa: F811
    response = serving.post(URL, json={"game_ids": [NEXT_GAME.id]})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "model_unavailable"


def test_score_forecast_uses_each_teams_earlier_games(league, scoring):  # noqa: F811
    body = scoring.post(URL, json={"game_ids": [NEXT_GAME.id]}).json()
    forecast = body[0]["forecast"]
    home, away = _team_points(league, 1), _team_points(league, 2)
    assert forecast["home"]["team_id"] == 1 and forecast["away"]["team_id"] == 2
    assert forecast["home"]["points"] == pytest.approx(np.mean(home[-10:]))
    assert forecast["away"]["points"] == pytest.approx(np.mean(away[-10:]))
    assert forecast["home"]["lower"] < forecast["home"]["points"] < forecast["home"]["upper"]
    margin = forecast["home"]["points"] - forecast["away"]["points"]
    assert (forecast["home_win_probability"] > 0.5) == (margin > 0)
    assert forecast["interval_level"] == 0.8


def test_repeating_returns_the_stored_forecast(league, scoring):  # noqa: F811
    first = scoring.post(URL, json={"game_ids": [NEXT_GAME.id]}).json()[0]["forecast"]
    again = scoring.post(URL, json={"game_ids": [NEXT_GAME.id, NEXT_GAME.id]}).json()
    assert len(again) == 1 and again[0]["forecast"]["id"] == first["id"]
    with Session(league) as s:
        assert s.scalar(select(func.count()).select_from(GamePrediction)) == 1


def test_new_results_append_a_superseding_forecast(league, scoring):  # noqa: F811
    first = scoring.post(URL, json={"game_ids": [LATER_GAME.id]}).json()[0]["forecast"]
    with league.begin() as conn:
        conn.execute(
            text("UPDATE team_game_stats SET pts = pts + 30 WHERE game_id = :g AND team_id = 1"),
            {"g": FINAL[-1].id},
        )
    second = scoring.post(URL, json={"game_ids": [LATER_GAME.id]}).json()[0]["forecast"]
    assert second["id"] != first["id"]
    assert second["supersedes_prediction_id"] == first["id"]
    assert second["home"]["points"] > first["home"]["points"]
    with Session(league) as s:
        assert s.scalar(select(func.count()).select_from(GamePrediction)) == 2


def test_games_that_cannot_be_forecast_say_why(scoring, monkeypatch):  # noqa: F811
    monkeypatch.setattr(game_forecasts, "MIN_PRIOR_GAMES", 50)
    final = EXTRA[0].id
    body = scoring.post(URL, json={"game_ids": [NEXT_GAME.id, final, "0099999999"]}).json()
    assert [entry["forecast"] for entry in body] == [None, None, None]
    codes = [entry["unavailable"]["code"] for entry in body]
    assert codes == ["insufficient_data", "game_already_started", "game_not_found"]


@pytest.mark.parametrize("ids", [[], ["123"], [str(i).zfill(10) for i in range(31)]])
def test_invalid_requests_are_refused(scoring, ids):  # noqa: F811
    assert scoring.post(URL, json={"game_ids": ids}).status_code == 422


def test_worker_stores_a_score_forecast_for_games_in_the_next_48_hours(league, tmp_path, scoring):  # noqa: F811
    result = maintain_predictions(league, NOW, tmp_path)
    assert result["game_forecasts"] >= 1
    with Session(league) as s:
        stored = set(s.scalars(select(GamePrediction.game_id)))
    assert NEXT_GAME.id in stored and LATER_GAME.id not in stored  # 2099-11-25 is outside 48 h
    again = maintain_predictions(league, NOW, tmp_path)
    assert again["game_forecasts"] == 0  # same inputs, nothing new stored


def test_review_shows_the_pregame_forecast_next_to_the_final_score(league, scoring):  # noqa: F811
    forecast = scoring.post(URL, json={"game_ids": [NEXT_GAME.id]}).json()[0]["forecast"]
    before = scoring.get(f"{URL}/{NEXT_GAME.id}").json()
    assert before["forecast"]["id"] == forecast["id"]
    assert before["home_score"] is None and before["picked_winner"] is None
    with league.begin() as conn:
        conn.execute(
            text(
                "UPDATE games SET status = 'final', home_score = 90, away_score = 120 WHERE id = :g"
            ),
            {"g": NEXT_GAME.id},
        )
    after = scoring.get(f"{URL}/{NEXT_GAME.id}").json()
    assert (after["home_score"], after["away_score"]) == (90, 120)
    assert after["forecast"]["id"] == forecast["id"]
    assert after["picked_winner"] == (forecast["home_win_probability"] < 0.5)


def test_review_without_a_stored_forecast_says_so(scoring):  # noqa: F811
    body = scoring.get(f"{URL}/{FINAL[0].id}").json()
    assert body["forecast"] is None and body["status"] == "final"
    assert scoring.get(f"{URL}/0099999999").status_code == 404


def _finish(engine: Engine, home: int, away: int, status: str = "final") -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE games SET status = :status, home_score = :home, away_score = :away, "
                "stats_finalized_at = :now WHERE id = :g"
            ),
            {"status": status, "home": home, "away": away, "now": NOW, "g": NEXT_GAME.id},
        )


def _change_inputs(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE team_game_stats SET pts = pts + 30 WHERE game_id = :g AND team_id = 1"),
            {"g": FINAL[-1].id},
        )


def _score(engine: Engine, now: datetime = NOW) -> int:
    with Session(engine) as s, s.begin():
        return game_forecasts.score_pending(s, now)


def _evaluations(engine: Engine) -> list[tuple]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT forecast_id::text, home_actual, away_actual, home_abs_error, "
                "away_abs_error, home_within_interval, away_within_interval, winner_correct, "
                "brier FROM game_prediction_evaluations ORDER BY forecast_id"
            )
        )
        return [tuple(r) for r in rows]


def test_changed_inputs_mark_the_forecast_stale_and_maintenance_refreshes_it(
    league,  # noqa: F811
    tmp_path,
    scoring,
):
    first = scoring.post(URL, json={"game_ids": [NEXT_GAME.id]}).json()[0]["forecast"]
    assert first["freshness"] == "current"
    assert scoring.get(f"{URL}/{NEXT_GAME.id}").json()["forecast"]["freshness"] == "current"
    _change_inputs(league)
    assert scoring.get(f"{URL}/{NEXT_GAME.id}").json()["forecast"]["freshness"] == "stale"
    assert maintain_predictions(league, NOW, tmp_path)["game_forecasts"] >= 1
    current = scoring.get(f"{URL}/{NEXT_GAME.id}").json()["forecast"]
    assert current["freshness"] == "current"
    assert current["supersedes_prediction_id"] == first["id"]
    with Session(league) as s:
        original = s.get(GamePrediction, uuid.UUID(first["id"]))
        assert original.home_pts == first["home"]["points"]
    assert maintain_predictions(league, NOW, tmp_path)["game_forecasts"] == 0


def test_forecasts_close_at_tip_off(league, tmp_path, scoring):  # noqa: F811
    first = scoring.post(URL, json={"game_ids": [NEXT_GAME.id]}).json()[0]["forecast"]
    after = NOW + timedelta(hours=7)
    scoring.app.state.api.clock = lambda: after
    _change_inputs(league)
    refused = scoring.post(URL, json={"game_ids": [NEXT_GAME.id]}).json()[0]
    assert refused["forecast"] is None
    assert refused["unavailable"]["code"] == "game_already_started"
    maintain_predictions(league, after, tmp_path)
    review = scoring.get(f"{URL}/{NEXT_GAME.id}").json()
    assert review["forecast"]["id"] == first["id"]
    assert review["forecast"]["freshness"] == "final_pregame"
    with Session(league) as s:
        assert s.scalar(select(func.count()).select_from(GamePrediction)
                        .where(GamePrediction.game_id == NEXT_GAME.id)) == 1  # fmt: skip


@pytest.mark.parametrize("status", ["postponed", "cancelled"])
def test_postponed_and_cancelled_games_are_never_scored(league, tmp_path, scoring, status):  # noqa: F811
    scoring.post(URL, json={"game_ids": [NEXT_GAME.id]})
    _finish(league, 100, 90, status)
    maintain_predictions(league, NOW, tmp_path)
    review = scoring.get(f"{URL}/{NEXT_GAME.id}").json()
    assert review["forecast"]["freshness"] == "invalid"
    assert status in review["forecast"]["freshness_reason"]
    assert review["evaluation"] is None
    assert _evaluations(league) == []
    with Session(league) as s, s.begin():
        assert game_forecasts.score_game(s, NEXT_GAME.id, NOW) == 0
    live = scoring.get(f"/api/v1/models/{VERSION}/live").json()
    assert live["game_scores"] is None


def test_live_metrics_count_only_the_final_forecast_and_match_hand_values(league, scoring):  # noqa: F811
    first = scoring.post(URL, json={"game_ids": [NEXT_GAME.id]}).json()[0]["forecast"]
    _change_inputs(league)
    final = scoring.post(URL, json={"game_ids": [NEXT_GAME.id]}).json()[0]["forecast"]
    assert final["id"] != first["id"]
    home, away = 100, 120
    _finish(league, home, away)
    assert _score(league) == 2

    home_miss = abs(final["home"]["points"] - home)
    away_miss = abs(final["away"]["points"] - away)
    inside = [
        final["home"]["lower"] <= home <= final["home"]["upper"],
        final["away"]["lower"] <= away <= final["away"]["upper"],
    ]
    probability = final["home_win_probability"]
    live = scoring.get(f"/api/v1/models/{VERSION}/live").json()["game_scores"]
    assert live["games"] == 1
    assert live["points_mae"] == pytest.approx((home_miss + away_miss) / 2)
    assert live["interval_coverage"] == pytest.approx(sum(inside) / 2)
    assert live["brier"] == pytest.approx(probability**2)
    assert live["winner_accuracy"] == (0.0 if probability >= 0.5 else 1.0)

    review = scoring.get(f"{URL}/{NEXT_GAME.id}").json()
    assert review["forecast"]["id"] == final["id"]
    assert review["evaluation"]["home_abs_error"] == pytest.approx(home_miss)
    assert review["evaluation"]["winner_correct"] == (probability < 0.5)


def test_repeated_scoring_changes_nothing(league, tmp_path, scoring):  # noqa: F811
    scoring.post(URL, json={"game_ids": [NEXT_GAME.id]})
    _finish(league, 100, 120)
    assert _score(league) == 1
    stored = _evaluations(league)
    assert _score(league) == 0
    assert maintain_predictions(league, NOW, tmp_path)["games_scored"] == 0
    assert _evaluations(league) == stored


def test_a_source_correction_updates_the_evaluation_not_the_forecast(league, tmp_path, scoring):  # noqa: F811
    forecast = scoring.post(URL, json={"game_ids": [NEXT_GAME.id]}).json()[0]["forecast"]
    _finish(league, 100, 120)
    _score(league)
    _finish(league, 130, 120)
    assert maintain_predictions(league, NOW, tmp_path)["games_scored"] == 1
    review = scoring.get(f"{URL}/{NEXT_GAME.id}").json()
    assert review["evaluation"]["home_abs_error"] == pytest.approx(
        abs(forecast["home"]["points"] - 130)
    )
    assert review["forecast"]["home"] == forecast["home"]
    assert review["forecast"]["created_at"] == forecast["created_at"]
    assert _evaluations(league)[0][1:3] == (130, 120)


def test_a_finalized_game_is_scored_by_its_sync_event(league, scoring):  # noqa: F811
    scoring.post(URL, json={"game_ids": [NEXT_GAME.id]})
    _finish(league, 100, 120)
    with Session(league) as s, s.begin():
        jobs.emit_event(s, SyncEventType.GAME_STATS_FINALIZED, "test-finalized",
                        {"game_id": NEXT_GAME.id}, None)  # fmt: skip
    drain_events(league, NOW)
    assert len(_evaluations(league)) == 1


def test_a_corrected_player_line_rescores_player_forecasts(league, scoring):  # noqa: F811
    response = scoring.post(
        "/api/v1/predictions", json={"player_id": STAR, "game_id": NEXT_GAME.id}
    )
    assert response.status_code == 201
    _finish(league, 100, 120)
    box = (
        "(game_id, player_id, team_id, minutes, fgm, fga, fg3m, fg3a, ftm, fta, oreb, dreb, reb, "
        "ast, stl, blk, tov, pf, pts, plus_minus, source_endpoint)"
    )
    with league.begin() as conn:
        conn.execute(
            text(
                f"INSERT INTO player_game_stats {box} "
                "VALUES (:g, :p, 1, 40, 5, 10, 0, 0, 0, 0, 0, 3, 3, 2, 1, 0, 1, 2, 10, 0, "
                "'fixture')"
            ),
            {"g": NEXT_GAME.id, "p": STAR},
        )
    with Session(league) as s, s.begin():
        prediction_lifecycle.score_game(s, NEXT_GAME.id, NOW)
    with league.begin() as conn:
        conn.execute(
            text(
                "UPDATE player_game_stats SET pts = 12, fgm = 6 "
                "WHERE game_id = :g AND player_id = :p"
            ),
            {"g": NEXT_GAME.id, "p": STAR},
        )
    with Session(league) as s, s.begin():
        jobs.emit_event(s, SyncEventType.HISTORICAL_DATA_CORRECTED, "test-corrected",
                        {"record_key": {"game_id": NEXT_GAME.id, "player_id": STAR},
                         "column": "pts"}, None)  # fmt: skip
    drain_events(league, NOW)
    with league.connect() as conn:
        actual = conn.scalar(text("SELECT actual FROM prediction_evaluations WHERE stat = 'pts'"))
    assert actual == 12
