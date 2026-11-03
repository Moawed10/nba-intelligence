import pytest

from tests.api.conftest import FINAL, RETIRED, SCHEDULED, SEASON_LABEL, STAR, player_id

pytestmark = pytest.mark.integration


def test_teams_list_and_detail(client):
    teams = client.get("/api/v1/teams").json()
    assert [t["city"] for t in teams] == ["Alpha", "Bravo", "Charlie"]
    detail = client.get("/api/v1/teams/1").json()
    assert detail["season"] == SEASON_LABEL
    assert detail["record"] == {"wins": 2, "losses": 2}
    assert len(detail["roster"]) == 5
    assert detail["roster"][0]["team"]["abbreviation"] == "AAA"


def test_team_stats_use_shared_definitions(client):
    body = client.get("/api/v1/teams/1/stats").json()
    possessions = 40 - 5 + 5 + 0.44 * 10
    assert body["games"] == 4
    assert body["pts_per_game"] == 60.0 and body["opp_pts_per_game"] == 60.0
    assert body["possessions_per_game"] == round(possessions, 1)
    assert body["offensive_rating"] == round(60 / possessions * 100, 1)
    assert body["pace"] == round(48 * possessions / (240 / 5), 1)
    assert body["net_rating"] == 0.0


def test_team_stats_without_games_return_nulls_not_zeros(client):
    body = client.get("/api/v1/teams/1/stats", params={"season_type": "playoffs"}).json()
    assert body["games"] == 0
    assert body["pts_per_game"] is None and body["pace"] is None
    assert body["shooting"]["fg_pct_status"] == "no_attempts"


@pytest.mark.parametrize(
    ("path", "status", "code"),
    [
        ("/api/v1/teams/99", 404, "team_not_found"),
        ("/api/v1/teams/99/stats", 404, "team_not_found"),
        ("/api/v1/teams/1?season=1999-00", 400, "invalid_parameter"),
        ("/api/v1/teams/0", 422, "validation_error"),
        ("/api/v1/teams/1/stats?season_type=preseason", 422, "validation_error"),
    ],
)
def test_team_errors(client, path, status, code):
    response = client.get(path)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_games_default_to_the_nba_day_and_filter(client):
    assert client.get("/api/v1/games").json()["total"] == 0
    month = {"date_from": "2099-11-01", "date_to": "2099-11-30"}
    page = client.get("/api/v1/games", params={**month, "limit": 3}).json()
    assert page["total"] == 8 and [g["id"] for g in page["items"]] == [g.id for g in FINAL[:3]]
    assert client.get("/api/v1/games", params={**month, "team_id": 2}).json()["total"] == 5
    assert client.get("/api/v1/games", params={**month, "status": "final"}).json()["total"] == 5
    first = page["items"][0]
    assert first["home"]["score"] == 65 and first["away"]["team"]["abbreviation"] == "BBB"


@pytest.mark.parametrize(
    ("params", "status"),
    [
        ({"date_from": "2099-01-01", "date_to": "2099-03-01"}, 400),
        ({"date_from": "2099-11-02", "date_to": "2099-11-01"}, 400),
        ({"status": "finished"}, 422),
        ({"limit": 101}, 422),
    ],
)
def test_games_reject_invalid_windows(client, params, status):
    assert client.get("/api/v1/games", params=params).status_code == status


def test_upcoming_games(client):
    ids = [g["id"] for g in client.get("/api/v1/games/upcoming").json()]
    assert ids == [SCHEDULED[0].id, SCHEDULED[1].id]
    assert len(client.get("/api/v1/games/upcoming", params={"days": 14}).json()) == 2
    team3 = client.get("/api/v1/games/upcoming", params={"player_id": player_id(3, 0)}).json()
    assert [g["id"] for g in team3] == [SCHEDULED[1].id]
    assert client.get("/api/v1/games/upcoming", params={"player_id": RETIRED}).json() == []
    assert client.get("/api/v1/games/upcoming", params={"player_id": 12345}).status_code == 404
    assert client.get("/api/v1/games/upcoming", params={"days": 15}).status_code == 422


def test_game_detail_and_cache_headers(client):
    final = client.get(f"/api/v1/games/{FINAL[0].id}")
    assert final.json()["status"] == "final" and final.json()["stats_finalized"] is False
    assert final.headers["Cache-Control"] == "no-cache"
    scheduled = client.get(f"/api/v1/games/{SCHEDULED[0].id}").json()
    assert scheduled["home"]["score"] is None and scheduled["status"] == "scheduled"


def test_boxscore(client):
    body = client.get(f"/api/v1/games/{FINAL[0].id}/boxscore").json()
    home, away = body["teams"]
    assert home["is_home"] and home["totals"]["pts"] == 65 and away["totals"]["pts"] == 55
    assert len(home["players"]) == 5 and home["minutes"] == 240
    star = next(p for p in home["players"] if p["player_id"] == STAR)
    assert star["double_double"] is True and star["box"]["pts"] == 26


@pytest.mark.parametrize(
    ("path", "status", "code"),
    [
        (f"/api/v1/games/{SCHEDULED[0].id}/boxscore", 409, "game_not_final"),
        ("/api/v1/games/0029999999", 404, "game_not_found"),
        ("/api/v1/games/0029999999/boxscore", 404, "game_not_found"),
        ("/api/v1/games/abc", 422, "validation_error"),
    ],
)
def test_game_errors(client, path, status, code):
    response = client.get(path)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/overview",
        "/api/v1/leaders",
        "/api/v1/players",
        f"/api/v1/players/{STAR}",
        f"/api/v1/players/{STAR}/stats",
        f"/api/v1/players/{STAR}/career",
        "/api/v1/teams/1/stats",
        "/api/v1/games",
        "/api/v1/models",
    ],
)
def test_every_data_response_is_revalidated_on_refresh(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-cache"


def test_home_court_splits_add_up_to_the_season(client):
    body = client.get("/api/v1/teams/1/home-court").json()
    stats = client.get("/api/v1/teams/1/stats").json()
    assert body["home"]["games"] + body["away"]["games"] == stats["games"]
    assert body["home"]["wins"] + body["away"]["wins"] == stats["record"]["wins"]
    assert body["average_attendance"] is None and body["attendance_games"] == 0
    for player in body["players"]:
        assert player["home_games"] + player["away_games"] > 0
        if player["home_games"] == 0:
            assert player["home"]["pts"] is None

