from datetime import UTC, datetime

import pandas as pd
import pytest

from app.ingestion.transforms import (
    current_season_start_year,
    parse_height,
    parse_matchup,
    season_from_game_id,
    season_label,
    transform_matchups,
    transform_player_logs,
    transform_schedule,
    transform_team_logs,
    validate_box,
)
from app.models import GameStatus, SeasonType
from tests.fixtures import BOX, FixtureGame, player_log, schedule, team_log

GAMES = [FixtureGame(1, "2099-11-01", home=1, away=2), FixtureGame(2, "2099-11-02", home=3, away=1)]


def _line(**overrides):
    line = {k.lower(): v for k, v in BOX.items()}
    line.update(overrides)
    return line


def test_matchup_parsing():
    assert parse_matchup("AAA vs. BBB") == (True, "BBB")
    assert parse_matchup("AAA @ BBB") == (False, "BBB")
    with pytest.raises(ValueError):
        parse_matchup("AAA - BBB")


def test_season_helpers():
    assert season_label(2025) == "2025-26"
    assert season_label(2099) == "2099-00"
    assert season_from_game_id("0022500001") == 2025
    assert parse_height("6-2") == 74
    assert parse_height("") is None


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 10, 28, 12, tzinfo=UTC), 2026),
        (datetime(2026, 4, 15, 12, tzinfo=UTC), 2025),
        # 03:30 UTC on Aug 1 is still July 31 in New York.
        (datetime(2026, 8, 1, 3, 30, tzinfo=UTC), 2025),
        (datetime(2026, 8, 1, 4, 30, tzinfo=UTC), 2026),
    ],
)
def test_current_season_uses_new_york_time(now, expected):
    assert current_season_start_year(now) == expected


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({}, None),
        ({"pts": -1}, "negative pts"),
        ({"fgm": 9}, "made exceeds attempted"),
        ({"fg3m": 5, "fg3a": 9}, "three-pointers exceed field goals"),
        ({"reb": 5}, "reb != oreb + dreb"),
        ({"pts": 12}, "pts != 2*fgm + fg3m + ftm"),
        ({"ast": None}, "missing ast"),
    ],
)
def test_validate_box(overrides, reason):
    assert validate_box(_line(**overrides)) == reason


def test_team_logs_build_games_and_lines():
    result = transform_team_logs(team_log(GAMES), SeasonType.regular)
    assert not result.games.rejections
    first = next(g for g in result.games.rows if g["id"] == GAMES[0].id)
    assert (first["home_team_id"], first["away_team_id"]) == (1, 2)
    assert first["status"] == GameStatus.final and first["season_id"] == 2099
    assert len(result.team_stats.rows) == 4


def test_neutral_site_requires_schedule_home():
    neutral = [FixtureGame(3, "2099-12-01", home=2, away=3, neutral=True)]
    rejected = transform_team_logs(team_log(neutral), SeasonType.regular)
    assert [r.reason for r in rejected.games.rejections] == ["no distinct home/away"]

    resolved = transform_team_logs(team_log(neutral), SeasonType.regular, {neutral[0].id: 2})
    assert resolved.games.rows[0]["home_team_id"] == 2
    assert resolved.games.rows[0]["away_team_id"] == 3


def test_unfinished_game_and_wrong_prefix_rejected():
    df = team_log(GAMES)
    df.loc[GAMES[0].id == df.GAME_ID, "WL"] = None
    result = transform_team_logs(df, SeasonType.regular)
    assert {r.reason for r in result.games.rejections} == {"game not final"}

    playoffs = transform_team_logs(team_log(GAMES), SeasonType.playoffs)
    assert len(playoffs.games.rejections) == 2 and not playoffs.games.rows


def test_player_lines_validated_against_team_minutes():
    minutes = {(g.id, t): 240 for g in GAMES for t in (g.home, g.away)}
    ok = transform_player_logs(player_log(GAMES), minutes, minutes_tolerance=5)
    assert len(ok.stats.rows) == 20 and not ok.stats.rejections
    assert len(ok.players) == 15

    short = player_log(GAMES, {(GAMES[0].id, 100): {"MIN": 30}})
    result = transform_player_logs(short, minutes, minutes_tolerance=5)
    assert len(result.stats.rejections) == 5
    assert all("team minutes mismatch" in r.reason for r in result.stats.rejections)

    orphan = transform_player_logs(player_log(GAMES), {}, minutes_tolerance=5)
    assert {r.reason for r in orphan.stats.rejections} == {"game not in validated team logs"}


def test_schedule_filters_non_season_games_and_maps_status():
    games = [
        *GAMES,
        FixtureGame(9, "2099-10-01", 1, 2, prefix="001"),
        FixtureGame(10, "2099-12-17", 1, 2, prefix="006"),
    ]
    df = schedule(games, status=1)
    df.loc[df.gameId == GAMES[1].id, "postponedStatus"] = "Y"
    result = transform_schedule(df, datetime(2099, 10, 1, tzinfo=UTC))
    assert [r["id"] for r in result.rows] == [GAMES[0].id, GAMES[1].id]
    assert result.rows[0]["status"] == GameStatus.scheduled
    assert result.rows[1]["status"] == GameStatus.postponed
    assert result.rows[0]["tipoff_at"] == datetime(2099, 11, 1, 0, 30, tzinfo=UTC)
    assert "home_score" not in result.rows[0]


def test_schedule_rejects_undetermined_teams():
    df = schedule(GAMES[:1])
    df["awayTeam_teamId"] = 0
    result = transform_schedule(df, datetime.now(UTC))
    assert not result.rows and result.rejections[0].reason == "teams not yet determined"


def test_empty_frames():
    assert transform_team_logs(pd.DataFrame(), SeasonType.regular).games.rows == []


def _matchup_row(**overrides):
    row = {
        "teamId": 1, "personIdOff": 11, "personIdDef": 21, "matchupMinutesSort": 36.9,
        "partialPossessions": 2.7, "playerPoints": 4, "matchupAssists": 1, "matchupTurnovers": 0,
        "matchupFieldGoalsMade": 2, "matchupFieldGoalsAttempted": 3,
        "matchupThreePointersMade": 0, "matchupThreePointersAttempted": 1,
    }  # fmt: skip
    return {**row, **overrides}


def test_matchup_rows_name_both_teams_from_the_offensive_team():
    frame = pd.DataFrame([_matchup_row(), _matchup_row(teamId=2, personIdOff=21, personIdDef=11)])
    out = transform_matchups(frame, "0099000001", (1, 2), {11, 21})
    assert out.rejections == []
    assert [(r["off_team_id"], r["def_team_id"]) for r in out.rows] == [(1, 2), (2, 1)]
    assert out.rows[0]["partial_possessions"] == 2.7 and out.rows[0]["fg3a"] == 1


def test_matchup_rows_without_possessions_are_dropped_and_bad_rows_rejected():
    frame = pd.DataFrame(
        [
            _matchup_row(partialPossessions=0),
            _matchup_row(teamId=9),
            _matchup_row(personIdDef=99),
            _matchup_row(playerPoints=-1),
            _matchup_row(partialPossessions=None, personIdOff="not a number"),
        ]
    )
    out = transform_matchups(frame, "0099000001", (1, 2), {11, 21})
    assert out.rows == []
    assert len(out.rejections) == 4
