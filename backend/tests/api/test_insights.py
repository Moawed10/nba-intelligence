import pytest
from sqlalchemy.orm import Session

from app.ml.dataset import training_frame
from app.ml.models import FAST_CONFIG
from app.ml.train import report, train_release, write_release
from app.models import Season
from tests import ml_fixtures
from tests.api.conftest import FINAL, SCHEDULED, SEASON_LABEL, STAR

pytestmark = pytest.mark.integration


def test_standouts_rank_by_game_score(client):
    body = client.get("/api/v1/standouts", params={"limit": 3}).json()
    assert body["window_end"] == "2099-11-07" and body["window_start"] == "2099-11-01"
    top = body["performances"][0]
    assert (top["player_id"], top["game_id"]) == (STAR, FINAL[0].id)
    assert top["game_score"] == 24.8
    assert top["double_double"] is True and top["result"] == "W"
    assert body["performances"][1]["game_score"] < 24.8
    assert "Game Score" in body["criterion"]


def test_leaders_apply_the_qualifying_minimum(client):
    body = client.get("/api/v1/leaders", params={"stat": "pts", "limit": 3}).json()
    assert body["season"] == SEASON_LABEL
    assert body["minimum_games"] == 3
    assert body["qualified_players"] == 15
    assert body["leaders"][0]["player_id"] == STAR
    assert body["leaders"][0]["value"] == 14.75
    assert [leader["rank"] for leader in body["leaders"]] == [1, 2, 3]
    assert client.get("/api/v1/leaders", params={"stat": "tov"}).status_code == 422


def test_directory_averages_match_the_profile_statistics(client):
    page = client.get("/api/v1/players", params={"season": SEASON_LABEL, "sort": "-pts"}).json()
    assert page["total"] == 15
    first = page["items"][0]
    assert first["id"] == STAR
    stats = client.get(f"/api/v1/players/{STAR}/stats").json()["seasons"][0]
    for key in ("pts", "reb", "ast", "min", "fg3m"):
        assert first["season_averages"][key] == stats["per_game"][key]
    assert first["season_averages"]["games_played"] == stats["games_played"]
    assert first["season_averages"]["fg_pct"] == stats["shooting"]["fg_pct"]
    plain = client.get("/api/v1/players").json()["items"][0]
    assert plain["season_averages"] is None


def test_stat_sorting_requires_a_season(client):
    response = client.get("/api/v1/players", params={"sort": "-pts"})
    assert response.status_code == 400
    assert response.json()["error"]["details"][0]["issue"] == "needs_season"


def test_overview_without_a_model_release(client):
    body = client.get("/api/v1/overview").json()
    assert body["today"] == "2099-11-10"
    assert [g["id"] for g in body["upcoming"]] == [SCHEDULED[0].id, SCHEDULED[1].id]
    assert [g["id"] for g in body["recent"]] == [FINAL[4].id]
    assert body["standouts"]["performances"][0]["player_id"] == STAR
    assert body["leaders"]["leaders"][0]["player_id"] == STAR
    assert body["model"] is None
    assert len(body["datasets"]) == 7
    assert client.get("/api/v1/models").json() == []
    assert client.get("/api/v1/models/2099.01.01-1").status_code == 404
    assert client.get("/api/v1/models/latest").status_code == 422


def test_model_registry_endpoints_report_recorded_evaluations(client, loaded, tmp_path):
    frame = training_frame(*ml_fixtures.league())
    result = train_release(frame, FAST_CONFIG, ml_fixtures.PLAN)
    with Session(loaded) as s, s.begin():
        s.add_all([Season(id=y, label=f"{y}-{(y + 1) % 100:02d}") for y in ml_fixtures.SEASONS])
    summary = report(result, data_version=7, leakage=0, rows=len(frame))
    version = write_release(result, summary, loaded, tmp_path, data_version=7)
    client.app.state.api.reset()

    releases = client.get("/api/v1/models").json()
    assert [r["version"] for r in releases] == [version]
    assert releases[0]["status"] == "candidate"
    detail = client.get(f"/api/v1/models/{version}").json()
    assert detail["test_season"] == "2093-94"
    assert {m["target"] for m in detail["selected_metrics"]} == {
        "pts", "reb", "ast", "fg3m", "stl", "blk", "min", "double_double",
    }  # fmt: skip
    pts = next(m for m in detail["selected_metrics"] if m["target"] == "pts")
    expected = result.targets["pts"].scores[result.targets["pts"].selected]["test"]
    assert pts["mae"] == pytest.approx(expected["mae"])
    assert pts["baseline_mae"] == pytest.approx(expected["baseline_mae"])
    assert pts["interval_coverage"] == pytest.approx(result.targets["pts"].test_coverage["overall"])
    assert len([a for a in detail["algorithms"] if a["target"] == "pts"]) == 4
    assert len(detail["features"]) == 60
    assert set(detail["interval_calibration"]) == {"pts", "reb", "ast", "fg3m", "stl", "blk", "min"}

    overview = client.get("/api/v1/overview").json()
    assert overview["model"]["release"]["version"] == version
