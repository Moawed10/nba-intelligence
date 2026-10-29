import pytest
from sqlalchemy import text

from tests.api.conftest import NO_SHOTS, RETIRED, SEASON_LABEL, STAR

pytestmark = pytest.mark.integration


def error_code(response) -> str:
    return response.json()["error"]["code"]


def test_directory_paginates_filters_and_sorts(client):
    page = client.get("/api/v1/players", params={"limit": 5}).json()
    assert (page["total"], page["limit"], page["offset"], len(page["items"])) == (16, 5, 0, 5)
    assert page["items"][0]["full_name"] == "Nikola Testić"
    assert page["meta"]["data_freshness"]["dataset"] == "player_game_logs"

    assert client.get("/api/v1/players", params={"team_id": 1}).json()["total"] == 5
    inactive = client.get("/api/v1/players", params={"active": False}).json()
    assert [p["id"] for p in inactive["items"]] == [RETIRED]
    assert client.get("/api/v1/players", params={"season": SEASON_LABEL}).json()["total"] == 15
    desc = client.get("/api/v1/players", params={"sort": "-full_name"}).json()
    assert desc["items"][0]["full_name"] == "Test Player 304"
    last = client.get("/api/v1/players", params={"limit": 5, "offset": 15}).json()
    assert len(last["items"]) == 1


@pytest.mark.parametrize(
    ("params", "status", "code"),
    [
        ({"sort": "height"}, 422, "validation_error"),
        ({"limit": 101}, 422, "validation_error"),
        ({"offset": -1}, 422, "validation_error"),
        ({"season": "1999-00"}, 400, "invalid_parameter"),
        ({"season": "2099"}, 422, "validation_error"),
    ],
)
def test_directory_rejects_invalid_parameters(client, params, status, code):
    response = client.get("/api/v1/players", params=params)
    assert response.status_code == status
    assert error_code(response) == code


def test_search_is_accent_insensitive_and_ranks_active_players_first(client):
    for q in ("testic", "TESTIĆ", "nikola tes"):
        results = client.get("/api/v1/players/search", params={"q": q}).json()
        assert results[0]["full_name"] == "Nikola Testić", q
    names = [r["full_name"] for r in client.get("/api/v1/players/search?q=testic").json()]
    assert names == ["Nikola Testić", "Retired Testić"]
    assert len(client.get("/api/v1/players/search", params={"q": "player", "limit": 3}).json()) == 3


def test_search_treats_wildcards_literally(client):
    assert client.get("/api/v1/players/search", params={"q": "%%"}).json() == []
    assert client.get("/api/v1/players/search", params={"q": "__"}).json() == []


@pytest.mark.parametrize("params", [{"q": "a"}, {"q": "x" * 65}, {"q": "ab", "limit": 21}, {}])
def test_search_validates_input(client, params):
    response = client.get("/api/v1/players/search", params=params)
    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_profile_has_identity_season_summary_and_recent_games(client):
    body = client.get(f"/api/v1/players/{STAR}").json()
    assert body["player"]["full_name"] == "Nikola Testić"
    assert body["player"]["team"]["abbreviation"] == "AAA"
    season = body["current_season"]
    assert (season["season"], season["games_played"], season["per_game"]["pts"]) == (
        SEASON_LABEL, 4, 14.75,
    )  # fmt: skip
    assert season["totals"]["pts"] == 59
    assert season["shooting"]["fg_pct"] == round(22 / 39, 4)
    assert season["double_doubles"] == 1
    games = body["last_games"]
    assert [g["game_date"] for g in games] == [
        "2099-11-07",
        "2099-11-05",
        "2099-11-02",
        "2099-11-01",
    ]
    first = games[-1]
    assert (first["result"], first["team_score"], first["opponent_score"]) == ("W", 65, 55)
    assert first["double_double"] is True
    assert games[0]["result"] == "L" and games[0]["is_home"] is False


def test_profile_of_player_without_games(client):
    body = client.get(f"/api/v1/players/{RETIRED}").json()
    assert body["current_season"] is None
    assert body["last_games"] == []
    assert body["player"]["team"] is None


@pytest.mark.parametrize("path", ["", "/stats", "/games", "/trends"])
def test_unknown_player_returns_404(client, path):
    response = client.get(f"/api/v1/players/9999999{path}")
    assert response.status_code == 404
    assert error_code(response) == "player_not_found"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]


@pytest.mark.parametrize("player", ["0", "-1", "abc", "99999999999"])
def test_invalid_player_ids_are_rejected(client, player):
    response = client.get(f"/api/v1/players/{player}")
    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_season_stats_and_splits(client):
    body = client.get(f"/api/v1/players/{STAR}/stats").json()
    assert [(s["season"], s["games_played"]) for s in body["seasons"]] == [(SEASON_LABEL, 4)]
    splits = {s["key"]: s["summary"] for s in body["splits"]}
    assert {k: v["games_played"] for k, v in splits.items()} == {
        "home": 2, "away": 2, "rest_0": 1, "rest_1": 1, "rest_2_plus": 1,
    }  # fmt: skip
    assert splits["home"]["per_game"]["pts"] == 18.5
    playoffs = client.get(f"/api/v1/players/{STAR}/stats", params={"season_type": "playoffs"})
    assert playoffs.json()["seasons"] == [] and playoffs.json()["splits"] == []
    bad = client.get(f"/api/v1/players/{STAR}/stats", params={"season": "1999-00"})
    assert bad.status_code == 400


def test_game_log_filters_sorts_and_reports_missing_percentages(client):
    log = client.get(f"/api/v1/players/{STAR}/games").json()
    assert log["total"] == 4
    assert log["items"][0]["game_date"] == "2099-11-07"
    top = client.get(f"/api/v1/players/{STAR}/games", params={"sort": "-pts", "limit": 1}).json()
    assert top["items"][0]["box"]["pts"] == 26 and top["total"] == 4
    window = client.get(
        f"/api/v1/players/{STAR}/games", params={"date_from": "2099-11-05", "date_to": "2099-11-30"}
    ).json()
    assert window["total"] == 2
    page = client.get(f"/api/v1/players/{STAR}/games", params={"limit": 2, "offset": 2}).json()
    assert [g["game_date"] for g in page["items"]] == ["2099-11-02", "2099-11-01"]

    no_shots = client.get(
        f"/api/v1/players/{NO_SHOTS}/games", params={"date_to": "2099-11-02", "sort": "game_date"}
    ).json()["items"][1]
    assert no_shots["shooting"]["fg_pct"] is None
    assert no_shots["shooting"]["fg_pct_status"] == "no_attempts"


@pytest.mark.parametrize(
    ("params", "status"),
    [
        ({"date_from": "2099-11-05", "date_to": "2099-11-01"}, 400),
        ({"season": "1999-00"}, 400),
        ({"sort": "plus_minus"}, 422),
        ({"date_from": "not-a-date"}, 422),
        ({"limit": 0}, 422),
    ],
)
def test_game_log_rejects_invalid_parameters(client, params, status):
    assert client.get(f"/api/v1/players/{STAR}/games", params=params).status_code == status


def test_trends_use_previous_games_only(client):
    body = client.get(f"/api/v1/players/{STAR}/trends", params={"stat": "reb"}).json()
    assert body["season"] == SEASON_LABEL
    assert [p["value"] for p in body["points"]] == [12, 4, 4, 4]
    assert [p["rolling_3"] for p in body["points"]] == [None, None, None, 6.67]
    assert body["average"] == 6.0 and body["games_played"] == 4


@pytest.mark.parametrize(
    ("player", "params", "status"),
    [
        (STAR, {"stat": "plus_minus"}, 422),
        (STAR, {"season": "1999-00"}, 400),
        (RETIRED, {}, 400),
    ],
)
def test_trends_reject_invalid_requests(client, player, params, status):
    assert client.get(f"/api/v1/players/{player}/trends", params=params).status_code == status


def test_stat_sort_survives_players_who_only_had_did_not_play_lines(client, loaded):
    with loaded.begin() as conn:
        conn.execute(
            text("UPDATE player_game_stats SET minutes = 0 WHERE player_id = :p"), {"p": NO_SHOTS}
        )
    response = client.get(
        "/api/v1/players", params={"season": SEASON_LABEL, "sort": "-pts", "limit": 50}
    )
    assert response.status_code == 200
    rows = {p["id"]: p for p in response.json()["items"]}
    assert rows[NO_SHOTS]["season_averages"]["games_played"] == 0
    assert rows[NO_SHOTS]["season_averages"]["pts"] is None
    assert list(rows)[-1] == NO_SHOTS  # no per-game value sorts last
