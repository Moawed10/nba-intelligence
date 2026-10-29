"""Statistic definitions checked against hand-computed values (docs/data-ownership.md)."""

from dataclasses import replace
from datetime import date

import pytest

from app import stats
from app.stats import Line

BASE = Line(
    game_date=date(2099, 1, 1), minutes=30.0, pts=0, reb=0, ast=0, fg3m=0, stl=0, blk=0,
    tov=0, oreb=0, dreb=0, pf=0, fgm=0, fga=0, fg3a=0, ftm=0, fta=0,
)  # fmt: skip


def line(day: int = 1, **values) -> Line:
    return replace(BASE, game_date=date(2099, 1, day), **values)


def test_ratio_reports_missing_attempts_instead_of_zero():
    assert stats.ratio(0, 0) == stats.Rate(None, "no_attempts")
    assert stats.ratio(1, 3) == stats.Rate(0.3333, None)


def test_effective_and_true_shooting():
    assert stats.efg_pct(4, 2, 10).value == 0.5
    assert stats.ts_pct(20, 10, 5).value == round(20 / (2 * (10 + 0.44 * 5)), 4)


def test_team_rate_definitions():
    assert stats.possessions(fga=90, oreb=10, tov=12, fta=20) == pytest.approx(100.8)
    assert stats.per_100(110, 100) == 110.0
    assert stats.per_100(10, 0) is None
    assert stats.pace(100, 240) == 100.0
    assert stats.pace(100, 0) is None


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ({"pts": 10, "reb": 10}, True),
        ({"stl": 10, "blk": 10}, True),
        ({"pts": 30, "reb": 9}, False),
        ({"pts": 10, "fg3m": 10}, False),
    ],
)
def test_double_double_counts_five_categories(values, expected):
    assert stats.is_double_double(line(**values)) is expected


def test_rest_days_cap_and_first_game():
    assert stats.rest_days(None, date(2099, 1, 1)) is None
    assert stats.rest_days(date(2099, 1, 1), date(2099, 1, 2)) == 0
    assert stats.rest_days(date(2099, 1, 1), date(2099, 3, 1)) == 7


def test_rest_series_ignores_games_not_played():
    lines = [line(1), line(2, minutes=0), line(4)]
    assert stats.rest_days_series(lines) == [None, 0, 2]


def test_rolling_average_excludes_current_game():
    assert stats.rolling_previous([10, 20, 30, 40], 2) == [None, None, 15.0, 25.0]


def test_coefficient_of_variation():
    assert stats.coefficient_of_variation([10]) is None
    assert stats.coefficient_of_variation([0, 0]) is None
    assert stats.coefficient_of_variation([10, 30]) == 0.5


def test_aggregate_uses_totals_and_games_played():
    lines = [
        line(1, fgm=1, fga=1, pts=2),
        line(2, fgm=0, fga=9, pts=0),
        line(3, minutes=0),
    ]
    agg = stats.aggregate(lines)
    assert agg.games_played == 2
    assert agg.fg_pct.value == 0.1
    assert agg.per_game["pts"] == 1.0
    assert agg.ft_pct == stats.Rate(None, "no_attempts")
    assert agg.totals["min"] == 60.0


def test_aggregate_of_no_games():
    agg = stats.aggregate([])
    assert agg.games_played == 0
    assert agg.per_game["pts"] is None
    assert agg.ts_pct.status == "no_attempts"
