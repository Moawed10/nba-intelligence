import pytest
from fastapi.testclient import TestClient

from app.services.rate_limit import PredictionLimiter, TokenBuckets, client_address
from tests.api.test_predictions import NEXT_GAME, STAR, client, league, serving  # noqa: F401

pytestmark = pytest.mark.integration

URL = "/api/v1/predictions"
BODY = {"player_id": STAR, "game_id": NEXT_GAME.id}


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def limited(serving: TestClient, clock: Clock) -> TestClient:  # noqa: F811
    state = serving.app.state.api
    state.limiter = PredictionLimiter(6, 2, 100, clock)
    state.trusted_proxies = {"testclient"}
    return serving


def test_requests_over_the_limit_get_a_predictable_429(limited, clock):
    assert limited.post(URL, json=BODY).status_code == 201
    assert limited.post(URL, json=BODY).status_code == 200
    refused = limited.post(URL, json=BODY)
    assert refused.status_code == 429
    assert refused.headers["Retry-After"] == "10"
    error = refused.json()["error"]
    assert error["code"] == "rate_limited"
    assert error["request_id"] == refused.headers["X-Request-ID"]
    clock.now = 9.9
    assert limited.post(URL, json=BODY).status_code == 429
    clock.now = 30.0
    assert limited.post(URL, json=BODY).status_code == 200


def test_every_prediction_post_shares_the_limit_and_reads_are_free(limited):
    assert limited.post(f"{URL}/upcoming", json={"player_id": STAR, "days": 3}).status_code == 200
    assert limited.post(f"{URL}/games", json={"game_ids": [NEXT_GAME.id]}).status_code != 429
    assert limited.post(URL, json=BODY).status_code == 429
    assert limited.post(f"{URL}/upcoming", json={"player_id": STAR}).status_code == 429
    assert limited.post(f"{URL}/games", json={"game_ids": [NEXT_GAME.id]}).status_code == 429
    for _ in range(5):
        assert limited.get(URL, params={"player_id": STAR}).status_code == 200


def test_clients_behind_a_trusted_proxy_are_limited_separately(limited):
    one = {"X-Forwarded-For": "203.0.113.1"}
    two = {"X-Forwarded-For": "203.0.113.2"}
    for _ in range(2):
        assert limited.post(URL, json=BODY, headers=one).status_code in (200, 201)
    assert limited.post(URL, json=BODY, headers=one).status_code == 429
    assert limited.post(URL, json=BODY, headers=two).status_code == 200


def test_the_global_limit_holds_when_clients_rotate_addresses(limited, clock):
    limited.app.state.api.limiter = PredictionLimiter(60, 2, 3, clock)
    statuses = [
        limited.post(URL, json=BODY, headers={"X-Forwarded-For": f"203.0.113.{i}"}).status_code
        for i in range(5)
    ]
    assert 429 not in statuses[:3] and statuses[3:] == [429, 429]


@pytest.mark.parametrize(
    ("peer", "header", "expected"),
    [
        ("10.0.0.1", "1.1.1.1", "10.0.0.1"),
        ("127.0.0.1", "1.1.1.1", "1.1.1.1"),
        ("127.0.0.1", "9.9.9.9, 1.1.1.1", "1.1.1.1"),
        ("127.0.0.1", "1.1.1.1, 127.0.0.1", "1.1.1.1"),
        ("127.0.0.1", None, "127.0.0.1"),
        (None, None, "unknown"),
    ],
)
def test_client_address_only_believes_trusted_peers(peer, header, expected):
    assert client_address(peer, header, {"127.0.0.1"}) == expected


def test_buckets_forget_refilled_clients(monkeypatch, clock):
    monkeypatch.setattr("app.services.rate_limit.MAX_TRACKED_CLIENTS", 2)
    buckets = TokenBuckets(60, 1, clock)
    buckets.take("a")
    buckets.take("b")
    clock.now = 10.0
    buckets.take("c")
    assert set(buckets.buckets) == {"c"}
