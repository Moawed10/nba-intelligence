import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import create_app
from app.services import teams
from tests.api.conftest import STAR

pytestmark = pytest.mark.integration

ENDPOINTS = {
    "/api/v1/players", "/api/v1/players/search", "/api/v1/players/{player_id}",
    "/api/v1/players/{player_id}/stats", "/api/v1/players/{player_id}/games",
    "/api/v1/players/{player_id}/trends", "/api/v1/teams", "/api/v1/teams/{team_id}",
    "/api/v1/teams/{team_id}/stats", "/api/v1/games", "/api/v1/games/upcoming",
    "/api/v1/games/{game_id}", "/api/v1/games/{game_id}/boxscore", "/api/v1/health",
    "/api/v1/readiness", "/api/v1/data-status",
}  # fmt: skip


def test_every_endpoint_is_documented_read_only(client):
    schema = client.get("/api/v1/openapi.json").json()
    assert set(schema["paths"]) == ENDPOINTS
    assert {m for ops in schema["paths"].values() for m in ops} == {"get"}


def test_health_and_readiness(client):
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    ready = client.get("/api/v1/readiness")
    assert ready.status_code == 200 and ready.json()["checks"]["database"] == "ok"
    assert ready.headers["Cache-Control"] == "no-store"


def test_database_outage_is_reported_without_details():
    engine = create_engine("postgresql+psycopg://127.0.0.1:1/unreachable")
    with TestClient(create_app(engine)) as down:
        ready = down.get("/api/v1/readiness")
        assert ready.status_code == 503 and ready.json()["status"] == "not_ready"
        data = down.get("/api/v1/players")
        assert data.status_code == 503
        assert data.json()["error"]["code"] == "database_unavailable"
        assert "127.0.0.1" not in data.text


def test_data_status(client, loaded):
    with loaded.connect() as conn:
        version = conn.scalar(text("SELECT max(id) FROM ingestion_runs"))
    body = client.get("/api/v1/data-status").json()
    assert body["data_version"] == version
    assert body["row_counts"] == {
        "games": 8, "players": 16, "teams": 3, "team_game_lines": 10, "player_game_lines": 50,
    }  # fmt: skip
    assert body["seasons"] == [
        {"season": "2099-00", "final_games": 5, "remaining_games": 3, "player_lines": 50}
    ]
    datasets = {d["dataset"]: d for d in body["datasets"]}
    assert set(datasets) == {"schedule", "final_box_scores", "player_game_logs", "season_stats",
                             "team_stats", "player_metadata"}  # fmt: skip
    assert datasets["player_game_logs"]["coverage_end"] == "2099-11-07"


def test_request_ids_are_echoed_or_generated(client):
    assert (
        client.get("/api/v1/health", headers={"X-Request-ID": "abc-123-def"}).headers[
            "X-Request-ID"
        ]
        == "abc-123-def"
    )
    generated = client.get("/api/v1/health", headers={"X-Request-ID": "bad id\n"}).headers[
        "X-Request-ID"
    ]
    assert uuid.UUID(generated)


def test_unknown_route_uses_error_envelope(client):
    response = client.get("/api/v1/nothing-here")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert client.post("/api/v1/teams").status_code == 405


def test_unexpected_errors_hide_internals(loaded, monkeypatch):
    def boom(ctx):
        raise RuntimeError("secret connection string")

    monkeypatch.setattr(teams, "list_teams", boom)
    with TestClient(create_app(loaded), raise_server_exceptions=False) as c:
        response = c.get("/api/v1/teams")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "secret" not in response.text


def test_freshness_meta_reports_stale_data(client):
    meta = client.get(f"/api/v1/players/{STAR}").json()["meta"]["data_freshness"]
    assert meta["is_stale"] is True and meta["status"] in {"stale", "unavailable"}
