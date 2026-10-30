"""GET /compare/players against the synthetic league (one regular season, 2099-00)."""

import pytest

from tests.api.conftest import RETIRED, STAR
from tests.fixtures import player_id

pytestmark = pytest.mark.integration

OTHER = player_id(2, 0)
URL = "/api/v1/compare/players"


def test_comparison_uses_the_same_season_lines_as_the_player_endpoints(client):
    body = client.get(URL, params={"p1": STAR, "p2": OTHER}).json()
    assert [p["id"] for p in body["players"]] == [STAR, OTHER]
    season = body["season"]
    assert season == "2099-00" and body["common_seasons"] == [season]
    for line, pid in zip(body["lines"], (STAR, OTHER), strict=True):
        stats = client.get(f"/api/v1/players/{pid}/stats").json()
        assert line == next(s for s in stats["seasons"] if s["season"] == season)


def test_radar_axes_are_league_percentiles_with_the_values_behind_them(client):
    body = client.get(URL, params={"p1": STAR, "p2": OTHER}).json()
    assert [a["key"] for a in body["axes"]] == ["pts", "reb", "ast", "fg3m", "stl", "blk", "ts_pct"]
    pts = next(a for a in body["axes"] if a["key"] == "pts")
    assert pts["values"][0] == pytest.approx(body["lines"][0]["per_game"]["pts"])
    for axis in body["axes"]:
        assert all(p is None or 0 <= p <= 100 for p in axis["percentiles"])
    assert body["qualified_players"] > 0 and "players with at least" in body["qualification"]


def test_swapping_players_swaps_every_value(client):
    a = client.get(URL, params={"p1": STAR, "p2": OTHER}).json()
    b = client.get(URL, params={"p1": OTHER, "p2": STAR}).json()
    assert a["lines"] == b["lines"][::-1]
    for x, y in zip(a["axes"], b["axes"], strict=True):
        assert x["percentiles"] == y["percentiles"][::-1] and x["values"] == y["values"][::-1]


def test_players_who_never_shared_a_season_get_no_numbers(client):
    body = client.get(URL, params={"p1": STAR, "p2": RETIRED}).json()
    assert body["season"] is None and body["lines"] == [] and body["axes"] == []


@pytest.mark.parametrize(
    ("params", "status", "code"),
    [
        ({"p1": STAR, "p2": STAR}, 400, "same_player"),
        ({"p1": STAR, "p2": 424242}, 404, "player_not_found"),
        ({"p1": STAR, "p2": OTHER, "season": "2050-51"}, 422, "no_common_season"),
        ({"p1": STAR, "p2": OTHER, "season": "bad"}, 422, None),
    ],
)
def test_invalid_comparisons_are_refused(client, params, status, code):
    response = client.get(URL, params=params)
    assert response.status_code == status
    if code:
        error = response.json()["error"]
        assert code in (error["code"], *(d.get("issue") for d in error.get("details", [])))
