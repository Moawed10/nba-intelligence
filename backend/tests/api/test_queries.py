"""Query-count and cache-invalidation checks for the Phase 4 performance gates."""

import pytest
from sqlalchemy import text

from tests.api.conftest import FINAL, STAR

pytestmark = pytest.mark.integration


def count(client, queries, path: str, **params) -> int:
    with queries() as counter:
        assert client.get(path, params=params).status_code == 200
    return counter.count


@pytest.mark.parametrize(
    ("path", "small", "large"),
    [
        ("/api/v1/players", {"limit": 2}, {"limit": 16}),
        (f"/api/v1/players/{STAR}/games", {"limit": 1}, {"limit": 4}),
        ("/api/v1/games", {"date_from": "2099-11-01", "date_to": "2099-11-30", "limit": 1},
         {"date_from": "2099-11-01", "date_to": "2099-11-30", "limit": 8}),
    ],
)  # fmt: skip
def test_list_queries_do_not_grow_with_page_size(client, queries, path, small, large):
    client.get("/api/v1/health")
    client.get("/api/v1/players", params={"limit": 1})
    assert count(client, queries, path, **small) == count(client, queries, path, **large)


def test_boxscore_uses_constant_queries(client, queries):
    client.get("/api/v1/players", params={"limit": 1})
    assert count(client, queries, f"/api/v1/games/{FINAL[0].id}/boxscore") <= 4


def test_cache_hits_skip_the_database_until_data_version_changes(client, queries, loaded):
    path = f"/api/v1/players/{STAR}"
    first = count(client, queries, path)
    assert count(client, queries, path) < first

    with loaded.begin() as conn:
        conn.execute(text("UPDATE players SET full_name = 'Renamed Testić' WHERE id = :id"),
                     {"id": STAR})  # fmt: skip
    state = client.app.state.api
    state.version.clear()
    assert client.get(path).json()["player"]["full_name"] == "Nikola Testić"

    with loaded.begin() as conn:
        conn.execute(text("INSERT INTO ingestion_runs (job, status, finished_at) "
                          "VALUES ('players', 'succeeded', now())"))  # fmt: skip
    state.version.clear()
    assert client.get(path).json()["player"]["full_name"] == "Renamed Testić"
