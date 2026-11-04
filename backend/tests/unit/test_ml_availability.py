"""Who a team is missing: production from earlier games only, rotation players only."""

import pandas as pd
import pytest

from app.ml.availability import ROTATION_MINUTES, expected_lines, team_absences


def _lines(games: int, players: dict[int, float], sits: dict[int, set[int]] | None = None):
    """Team 1's season: each player has fixed minutes and scores one point per minute."""
    rows = []
    for g in range(games):
        for player, minutes in players.items():
            if g in (sits or {}).get(player, set()):
                continue
            rows.append({
                "game_id": f"g{g}", "game_date": pd.Timestamp("2099-10-20") + pd.Timedelta(days=g),
                "season_id": 2099, "team_id": 1, "player_id": player, "minutes": minutes,
                "pts": minutes, "reb": 1, "ast": 1, "fga": 1,
            })  # fmt: skip
    return pd.DataFrame(rows)


def _game(absences: pd.DataFrame, game: str) -> pd.Series:
    return absences.set_index("game_id").loc[game]


def test_a_rotation_player_who_sits_counts_at_his_recent_production():
    lines = _lines(6, {1: 30.0, 2: 20.0}, sits={1: {5}})
    row = _game(team_absences(lines), "g5")
    assert row["absent_min"] == pytest.approx(30.0)
    assert row["absent_pts"] == pytest.approx(30.0)


def test_a_player_already_out_counts_less_as_the_team_adjusts():
    lines = _lines(8, {1: 30.0, 2: 20.0}, sits={1: {5, 6, 7}})
    absences = team_absences(lines)
    assert _game(absences, "g5")["absent_min"] > _game(absences, "g7")["absent_min"] > 0


def test_a_deep_reserve_sitting_is_not_an_absence():
    minutes = ROTATION_MINUTES - 1
    lines = _lines(6, {1: 30.0, 2: minutes}, sits={2: {5}})
    assert _game(team_absences(lines), "g5")["absent_min"] == 0


def test_the_absent_game_itself_never_adds_to_production():
    lines = _lines(6, {1: 30.0, 2: 20.0, 3: 20.0}, sits={1: {5}})
    before = _game(team_absences(lines), "g5")
    lines.loc[lines["game_id"] == "g5", ["minutes", "pts"]] = [40.0, 60]
    pd.testing.assert_series_equal(before, _game(team_absences(lines), "g5"))


def test_the_first_game_of_a_season_has_no_absences():
    lines = _lines(3, {1: 30.0})
    assert _game(team_absences(lines), "g0")["absent_min"] == 0


def test_serving_reads_absences_the_same_way_as_training():
    full = _lines(6, {1: 30.0, 2: 20.0, 3: 25.0}, sits={1: {5}})
    earlier = full[full["game_id"] != "g5"]
    served = expected_lines(
        earlier, game_id="g5", game_date=pd.Timestamp("2099-10-25"), season_id=2099,
        unavailable={(1, 1)},
    )  # fmt: skip
    pd.testing.assert_series_equal(
        _game(team_absences(full), "g5"), _game(team_absences(served), "g5")
    )


def test_a_traded_player_only_sits_for_his_old_team():
    earlier = pd.concat(
        [
            _lines(5, {1: 30.0}),
            _lines(5, {1: 30.0}).assign(team_id=2, game_id=lambda d: "t" + d["game_id"]),
        ]
    )
    served = expected_lines(
        earlier, game_id="g5", game_date=pd.Timestamp("2099-10-25"), season_id=2099,
        unavailable={(1, 1)},
    )  # fmt: skip
    tonight = served[served["game_id"] == "g5"]
    assert list(tonight["team_id"]) == [2]
