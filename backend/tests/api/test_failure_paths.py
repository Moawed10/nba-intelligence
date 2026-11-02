import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url, text

from app.db import api_engine
from app.main import create_app
from app.ml import inference
from app.services import players, prediction_lifecycle
from tests.api.test_predictions import NEXT_GAME, STAR, client, league, serving  # noqa: F401
from tests.conftest import TEST_URL

pytestmark = pytest.mark.integration

URL = "/api/v1/predictions"
BODY = {"player_id": STAR, "game_id": NEXT_GAME.id}
DEAD_DATABASE = "postgresql+psycopg://nobody:hunter2@127.0.0.1:1/missing"


def _assert_nothing_internal(response) -> None:
    for secret in (
        "hunter2",
        "/tmp",
        "/private",
        ".joblib",
        "Traceback",
        "psycopg",
        "site-packages",
    ):
        assert secret not in response.text


def test_a_database_outage_is_a_controlled_503():
    engine = create_engine(DEAD_DATABASE, connect_args={"connect_timeout": 1})
    with TestClient(create_app(engine), raise_server_exceptions=False) as test_client:
        for path in ("/api/v1/teams", "/api/v1/players/1"):
            response = test_client.get(path)
            assert response.status_code == 503
            assert response.json()["error"]["code"] == "database_unavailable"
            _assert_nothing_internal(response)
        predict = test_client.post(URL, json=BODY)
        assert predict.status_code == 503
        _assert_nothing_internal(predict)
        assert test_client.get("/api/v1/readiness").status_code == 503
        assert test_client.get("/api/v1/health").status_code == 200


def test_an_exhausted_connection_pool_is_a_controlled_503():
    engine = create_engine(TEST_URL, pool_size=1, max_overflow=0, pool_timeout=0.1)
    with engine.connect(), TestClient(create_app(engine)) as test_client:
        response = test_client.get("/api/v1/teams")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_busy"


@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_missing_or_corrupt_artifacts_stop_forecasts_without_naming_files(
    serving,  # noqa: F811
    tmp_path,
    damage,
):
    inference.clear_cache()
    artifact = sorted(tmp_path.rglob("*.joblib"))[0]
    if damage == "missing":
        artifact.unlink()
    else:
        artifact.write_bytes(artifact.read_bytes() + b"x")
    response = serving.post(URL, json=BODY)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "model_unavailable"
    _assert_nothing_internal(response)
    assert artifact.name not in response.text


def test_no_active_release_is_a_named_503(client):  # noqa: F811
    response = client.post(URL, json=BODY)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "model_unavailable"


def test_inference_overload_answers_quickly_with_503(serving, monkeypatch):  # noqa: F811
    monkeypatch.setattr(prediction_lifecycle, "INFERENCE_WAIT_SECONDS", 0)
    monkeypatch.setattr(prediction_lifecycle, "_inference_slots", threading.BoundedSemaphore(1))
    prediction_lifecycle._inference_slots.acquire()
    response = serving.post(URL, json=BODY)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "inference_busy"


def test_an_unexpected_error_reveals_nothing(serving, monkeypatch, caplog):  # noqa: F811
    def boom(*args, **kwargs):
        raise RuntimeError(f"failed at /private/secret with {DEAD_DATABASE}")

    monkeypatch.setattr(players, "search_players", boom)
    with TestClient(serving.app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/api/v1/players/search", params={"q": "abc"})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    _assert_nothing_internal(response)


def test_the_api_engine_limits_connection_time_and_statement_time():
    api_engine.cache_clear()
    engine = api_engine(TEST_URL)
    with engine.connect() as conn:
        assert conn.scalar(text("SHOW statement_timeout")) == "15s"
    assert make_url(TEST_URL).database == engine.url.database
    engine.dispose()
    api_engine.cache_clear()
