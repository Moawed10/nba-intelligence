"""Single implementation of every derived statistic.

Definitions are in docs/data-ownership.md#statistic-definitions. The API and the ML feature
pipeline both import from here.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from statistics import fmean, pstdev
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

COUNTING = ("pts", "reb", "ast", "fg3m", "stl", "blk", "tov", "oreb", "dreb", "pf",
            "fgm", "fga", "fg3a", "ftm", "fta")  # fmt: skip
AVERAGED = ("pts", "reb", "ast", "fg3m", "stl", "blk", "tov", "min")
DOUBLE_DOUBLE_STATS = ("pts", "reb", "ast", "stl", "blk")
REST_CAP_DAYS = 7
NO_ATTEMPTS = "no_attempts"


@dataclass(frozen=True)
class Line:
    game_date: date
    minutes: float
    pts: int
    reb: int
    ast: int
    fg3m: int
    stl: int
    blk: int
    tov: int
    oreb: int
    dreb: int
    pf: int
    fgm: int
    fga: int
    fg3a: int
    ftm: int
    fta: int

    @property
    def played(self) -> bool:
        return self.minutes > 0

    def value(self, stat: str) -> float:
        return self.minutes if stat == "min" else getattr(self, stat)


@dataclass(frozen=True)
class Rate:
    value: float | None
    status: str | None


def ratio(numerator: float, denominator: float) -> Rate:
    if denominator <= 0:
        return Rate(None, NO_ATTEMPTS)
    return Rate(round(numerator / denominator, 4), None)


def efg_pct(fgm: float, fg3m: float, fga: float) -> Rate:
    return ratio(fgm + 0.5 * fg3m, fga)


def ts_pct(pts: float, fga: float, fta: float) -> Rate:
    return ratio(pts, 2 * (fga + 0.44 * fta))


def possessions(fga: float, oreb: float, tov: float, fta: float) -> float:
    return fga - oreb + tov + 0.44 * fta


def per_100(points: float, poss: float) -> float | None:
    return round(points / poss * 100, 1) if poss > 0 else None


def pace(poss: float, team_minutes: float) -> float | None:
    """Possessions per 48 minutes; team minutes are summed over five players on court."""
    return round(48 * poss / (team_minutes / 5), 1) if team_minutes > 0 else None


def is_double_double(line: Line) -> bool:
    return sum(line.value(s) >= 10 for s in DOUBLE_DOUBLE_STATS) >= 2


def rest_days(previous: date | None, current: date) -> int | None:
    if previous is None:
        return None
    return min(max((current - previous).days - 1, 0), REST_CAP_DAYS)


def rest_days_series(lines: Sequence[Line]) -> list[int | None]:
    """Lines in date order; days since the player's previous game played."""
    result: list[int | None] = []
    previous: date | None = None
    for line in lines:
        result.append(rest_days(previous, line.game_date))
        if line.played:
            previous = line.game_date
    return result


def rolling_previous(values: Sequence[float], n: int) -> list[float | None]:
    """Mean of the previous n values, excluding the current one."""
    return [round(fmean(values[i - n : i]), 2) if i >= n else None for i in range(len(values))]


def coefficient_of_variation(values: Sequence[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = fmean(values)
    return round(pstdev(values) / mean, 3) if mean > 0 else None


@dataclass(frozen=True)
class Aggregate:
    games_played: int
    totals: dict[str, float]
    per_game: dict[str, float | None]
    fg_pct: Rate
    fg3_pct: Rate
    ft_pct: Rate
    efg_pct: Rate
    ts_pct: Rate
    double_doubles: int
    pts_consistency: float | None


def aggregate(lines: Sequence[Line]) -> Aggregate:
    played = [line for line in lines if line.played]
    games = len(played)
    totals: dict[str, float] = {s: sum(getattr(line, s) for line in played) for s in COUNTING}
    totals["min"] = round(sum(line.minutes for line in played), 2)
    return Aggregate(
        games_played=games,
        totals=totals,
        per_game={s: round(totals[s] / games, 2) if games else None for s in AVERAGED},
        fg_pct=ratio(totals["fgm"], totals["fga"]),
        fg3_pct=ratio(totals["fg3m"], totals["fg3a"]),
        ft_pct=ratio(totals["ftm"], totals["fta"]),
        efg_pct=efg_pct(totals["fgm"], totals["fg3m"], totals["fga"]),
        ts_pct=ts_pct(totals["pts"], totals["fga"], totals["fta"]),
        double_doubles=sum(is_double_double(line) for line in played),
        pts_consistency=coefficient_of_variation([line.pts for line in played]),
    )


def double_double_flags(frame: "pd.DataFrame") -> "pd.Series":
    """Vectorized is_double_double over a frame with the DOUBLE_DOUBLE_STATS columns."""
    return (frame[list(DOUBLE_DOUBLE_STATS)] >= 10).sum(axis=1) >= 2


def rest_days_from_gap(days_since_previous: "pd.Series") -> "pd.Series":
    """Vectorized rest_days: gap minus 1, clipped to [0, REST_CAP_DAYS]; no previous game -> cap."""
    return (days_since_previous - 1).clip(lower=0, upper=REST_CAP_DAYS).fillna(REST_CAP_DAYS)


def game_score(line: Line) -> float:
    """John Hollinger's Game Score: a single-number summary of one box score."""
    return round(
        line.pts + 0.4 * line.fgm - 0.7 * line.fga - 0.4 * (line.fta - line.ftm)
        + 0.7 * line.oreb + 0.3 * line.dreb + line.stl + 0.7 * line.ast + 0.7 * line.blk
        - 0.4 * line.pf - line.tov,
        1,
    )  # fmt: skip


def per_game(total: float, games: int) -> float | None:
    return round(total / games, 2) if games else None


LEADER_QUALIFYING_SHARE = 0.7


def leader_minimum_games(max_team_games: int) -> int:
    """Leaderboards require 70% of the most games any team has played this season."""
    return max(1, math.ceil(LEADER_QUALIFYING_SHARE * max_team_games))
