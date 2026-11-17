"""Live box scores: the cdn.nba.com feed through live_boxscore.py to GET /games/{id}/boxscore."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.ingestion.live_boxscore import (
    box_snapshot,
    clock,
    minutes,
    poll_live_box_scores,
)
from app.models import Game, GameStatus
from tests.api.conftest import SCHEDULED
from tests.fixtures import player_id

pytestmark = pytest.mark.integration

NOW = datetime(2099, 11, 11, 1, 30, tzinfo=UTC)
GAME = SCHEDULED[0]  # Alpha Ants (1) host Bravo Bears (2)


def _player(pid: int, played: str = "1", **stats) -> dict:
    line = {"minutes": "PT22M27.00S", "points": 14, "reboundsTotal": 6, "reboundsOffensive": 1,
            "reboundsDefensive": 5, "assists": 2, "fieldGoalsMade": 5, "fieldGoalsAttempted": 11,
            "threePointersMade": 3, "threePointersAttempted": 6, "freeThrowsMade": 1,
            "freeThrowsAttempted": 2, "plusMinusPoints": -4.0, **stats}  # fmt: skip
    return {"personId": pid, "name": f"Player {pid}", "starter": "1", "oncourt": "1",
            "played": played, "statistics": line}  # fmt: skip


def _team(team_id: int, *players: dict) -> dict:
    totals = {"minutes": "PT144M00.00S", "points": 70, "reboundsTotal": 30}
    return {"teamId": team_id, "players": list(players), "statistics": totals}


def feed(status: int = 2) -> dict:
    return {"game": {"gameId": GAME.id, "gameStatus": status, "period": 3,
                     "gameClock": "PT05M12.00S",
                     "homeTeam": _team(1, _player(player_id(1, 0), points=31, reboundsTotal=10,
                                                  assists=4), _player(player_id(1, 9), played="0")),
                     "awayTeam": _team(2, _player(player_id(2, 0)))}}  # fmt: skip


def test_feed_durations_and_clock_read_like_a_scoreboard():
    assert minutes("PT22M27.00S") == pytest.approx(22.45)
    assert minutes("") == 0.0
    assert clock("PT05M12.00S") == "5:12"
    assert clock("PT00M00.00S") == "0:00"
    assert clock(None) is None


def test_only_players_who_played_are_kept():
    snapshot = box_snapshot(feed())
    assert (snapshot["status"], snapshot["period"], snapshot["clock"]) == (2, 3, "5:12")
    home = next(t for t in snapshot["teams"] if t["is_home"])
    assert [p["player_id"] for p in home["players"]] == [player_id(1, 0)]
    assert home["players"][0]["pts"] == 31 and home["players"][0]["plus_minus"] == -4
    assert home["minutes"] == 144 and home["totals"]["pts"] == 70


@pytest.fixture
def live(loaded):
    with Session(loaded) as s, s.begin():
        s.execute(update(Game).where(Game.id == GAME.id).values(status=GameStatus.in_progress))
    assert poll_live_box_scores(loaded, lambda game_id: feed(), NOW) == 1
    return loaded


def test_a_game_in_progress_serves_the_live_snapshot(client, live):
    body = client.get(f"/api/v1/games/{GAME.id}/boxscore").json()
    assert body["live"]["period"] == 3 and body["live"]["clock"] == "5:12"
    assert body["stats_finalized"] is False
    assert [t["team"]["id"] for t in body["teams"]] == [1, 2]  # home first, as final box scores
    star = body["teams"][0]["players"][0]
    assert (star["box"]["pts"], star["box"]["reb"], star["double_double"]) == (31, 10, True)
    assert star["shooting"]["fg_pct"] == pytest.approx(5 / 11, abs=1e-4)


def test_each_poll_replaces_the_snapshot(client, live):
    later = feed()
    later["game"]["homeTeam"]["players"][0]["statistics"]["points"] = 35
    poll_live_box_scores(live, lambda game_id: later, NOW)
    body = client.get(f"/api/v1/games/{GAME.id}/boxscore").json()
    assert body["teams"][0]["players"][0]["box"]["pts"] == 35


def test_a_feed_that_says_final_does_not_overwrite_the_last_live_snapshot(client, live):
    done = feed(status=3)
    done["game"]["homeTeam"]["players"][0]["statistics"]["points"] = 99
    assert poll_live_box_scores(live, lambda game_id: done, NOW) == 0
    body = client.get(f"/api/v1/games/{GAME.id}/boxscore").json()
    assert body["teams"][0]["players"][0]["box"]["pts"] == 31


def test_a_game_in_progress_without_a_snapshot_has_no_box_score_yet(client, loaded):
    with Session(loaded) as s, s.begin():
        s.execute(update(Game).where(Game.id == GAME.id).values(status=GameStatus.in_progress))
    response = client.get(f"/api/v1/games/{GAME.id}/boxscore")
    assert response.status_code == 409
