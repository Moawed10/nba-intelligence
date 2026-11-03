import json
import random
from dataclasses import dataclass, field

import pytest
import requests
from nba_api.stats.endpoints import BoxScoreMatchupsV3, LeagueGameLog

from app.ingestion.client import (
    NBAStatsClient,
    NonRetryableSourceError,
    RetryableSourceError,
    UnexpectedResponseError,
    backoff_delay,
    parse_retry_after,
)

HEADERS = ["SEASON_ID", "PLAYER_ID", "GAME_ID", "PTS"]
BODY = json.dumps(
    {
        "resource": "leaguegamelog",
        "parameters": {},
        "resultSets": [
            {
                "name": "LeagueGameLog",
                "headers": HEADERS,
                "rowSet": [["22099", 1, "0029900001", 11]],
            }
        ],
    }
)


@dataclass
class FakeResponse:
    status_code: int = 200
    text: str = BODY
    headers: dict = field(default_factory=dict)


@dataclass
class FakeSession:
    responses: list
    calls: int = 0

    def get(self, url, params=None, headers=None, timeout=None):
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        if isinstance(response, Exception):
            raise response
        return response


def make_client(responses, tmp_path, **kwargs):
    sleeps: list[float] = []
    ticks = iter(range(0, 10_000, 10))
    client = NBAStatsClient(
        interval=1.0,
        timeout=5,
        max_attempts=5,
        backoff_base=1.0,
        backoff_cap=60.0,
        cache_dir=tmp_path,
        session=FakeSession(responses),
        sleep=sleeps.append,
        clock=lambda: next(ticks),
        rng=random.Random(7),
        **kwargs,
    )
    return client, sleeps


def fetch(client, **kw):
    return client.fetch(LeagueGameLog, season="2099-00", player_or_team_abbreviation="P", **kw)


def test_success_parses_frames(tmp_path):
    client, sleeps = make_client([FakeResponse()], tmp_path)
    result = fetch(client)
    assert result.attempts == 1 and not result.from_cache
    assert result.frames[0].iloc[0]["PTS"] == 11
    assert sleeps == []


@pytest.mark.parametrize(
    "failure",
    [
        FakeResponse(503),
        FakeResponse(429),
        FakeResponse(text="<html>busy</html>"),
        requests.Timeout(),
        requests.ConnectionError(),
    ],
)
def test_retryable_failures_then_success(tmp_path, failure):
    client, sleeps = make_client([failure, FakeResponse()], tmp_path)
    assert fetch(client).attempts == 2
    assert len(sleeps) == 1 and 0 <= sleeps[0] <= 1.0


def test_retry_after_is_honored(tmp_path):
    client, sleeps = make_client(
        [FakeResponse(429, headers={"Retry-After": "12"}), FakeResponse()], tmp_path
    )
    fetch(client)
    assert sleeps == [12.0]


def test_attempts_are_bounded(tmp_path):
    client, sleeps = make_client([FakeResponse(503)], tmp_path)
    with pytest.raises(RetryableSourceError):
        fetch(client)
    assert client.session.calls == 5
    assert len(sleeps) == 4


@pytest.mark.parametrize("status", [400, 403, 404])
def test_non_retryable_status_fails_immediately(tmp_path, status):
    client, sleeps = make_client([FakeResponse(status)], tmp_path)
    with pytest.raises(NonRetryableSourceError):
        fetch(client)
    assert client.session.calls == 1 and sleeps == []


def test_unexpected_schema_is_not_retried(tmp_path):
    bad = json.dumps({"resultSets": [{"name": "Other", "headers": [], "rowSet": []}]})
    client, _ = make_client([FakeResponse(text=bad)], tmp_path)
    with pytest.raises(NonRetryableSourceError):
        fetch(client, cacheable=True)
    assert not list(tmp_path.rglob("*.json")), "invalid responses must never be cached"


def test_a_v3_reply_with_no_tables_is_a_source_error_not_a_crash(tmp_path):
    client, _ = make_client([FakeResponse(text=json.dumps({"meta": {}}))], tmp_path)
    with pytest.raises(UnexpectedResponseError):
        client.fetch(BoxScoreMatchupsV3, game_id="0022600001", cacheable=True)
    assert not list(tmp_path.rglob("*.json")), "invalid responses must never be cached"


def test_cacheable_responses_are_reused(tmp_path):
    client, _ = make_client([FakeResponse()], tmp_path)
    fetch(client, cacheable=True)
    again = fetch(client, cacheable=True)
    assert again.from_cache and client.session.calls == 1


def test_throttle_spaces_requests(tmp_path):
    client, sleeps = make_client([FakeResponse()], tmp_path)
    client.clock = iter([0.0, 0.0, 0.25, 0.25]).__next__
    fetch(client)
    fetch(client)
    assert sleeps == [0.75]


def test_backoff_and_retry_after_parsing():
    rng = random.Random(1)
    assert all(0 <= backoff_delay(a, 1, 60, rng) <= min(60, 2 ** (a - 1)) for a in range(1, 10))
    assert backoff_delay(20, 1, 60, random.Random(0)) <= 60
    assert parse_retry_after("5") == 5.0
    assert parse_retry_after("soon") is None
    assert parse_retry_after(None) is None
