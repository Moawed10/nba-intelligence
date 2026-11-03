"""Synthetic test fixtures.

Every value here is invented. Season 2099 and team ids 1–3 cannot collide with real NBA records, so
fixture data is never mistaken for production statistics.
"""

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from app.ingestion.client import FetchResult

SEASON = 2099
TEAMS = [
    {"id": 1, "abbreviation": "AAA", "city": "Alpha", "name": "Ants"},
    {"id": 2, "abbreviation": "BBB", "city": "Bravo", "name": "Bears"},
    {"id": 3, "abbreviation": "CCC", "city": "Charlie", "name": "Cats"},
]
ABBR = {t["id"]: t["abbreviation"] for t in TEAMS}

BOX = {
    "FGM": 4,
    "FGA": 8,
    "FG3M": 1,
    "FG3A": 3,
    "FTM": 2,
    "FTA": 2,
    "OREB": 1,
    "DREB": 3,
    "REB": 4,
    "AST": 2,
    "STL": 1,
    "BLK": 0,
    "TOV": 1,
    "PF": 2,
    "PTS": 11,
}


def game_id(n: int, prefix: str = "002") -> str:
    return f"{prefix}{SEASON % 100:02d}{n:05d}"


@dataclass
class FixtureGame:
    number: int
    date: str
    home: int
    away: int
    neutral: bool = False
    prefix: str = "002"

    @property
    def id(self) -> str:
        return game_id(self.number, self.prefix)


def player_id(team: int, slot: int) -> int:
    return team * 100 + slot


def team_log(games: list[FixtureGame]) -> pd.DataFrame:
    rows = []
    for g in games:
        for team, opp, home in ((g.home, g.away, True), (g.away, g.home, False)):
            sep = " @ " if (g.neutral or not home) else " vs. "
            totals = {k: v * 5 for k, v in BOX.items()}
            rows.append(
                {
                    "SEASON_ID": f"2{SEASON}",
                    "TEAM_ID": team,
                    "TEAM_ABBREVIATION": ABBR[team],
                    "GAME_ID": g.id,
                    "GAME_DATE": g.date,
                    "MATCHUP": f"{ABBR[team]}{sep}{ABBR[opp]}",
                    "WL": "W" if home else "L",
                    "MIN": 240,
                    **totals,
                    "PLUS_MINUS": 0,
                }
            )
    return pd.DataFrame(rows)


def player_log(games: list[FixtureGame], overrides: dict[tuple[str, int], dict] | None = None):
    rows = []
    for g in games:
        for team in (g.home, g.away):
            for slot in range(5):
                pid = player_id(team, slot)
                row = {
                    "SEASON_ID": f"2{SEASON}",
                    "PLAYER_ID": pid,
                    "PLAYER_NAME": f"Test Player {pid}",
                    "TEAM_ID": team,
                    "GAME_ID": g.id,
                    "GAME_DATE": g.date,
                    "MIN": 48,
                    **BOX,
                    "PLUS_MINUS": 0,
                }
                row.update((overrides or {}).get((g.id, pid), {}))
                rows.append(row)
    return pd.DataFrame(rows)


def schedule(games: list[FixtureGame], status: int = 3, tipoff_hour: int = 0) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "gameId": g.id,
                "gameStatus": status,
                "gameStatusText": {1: "7:30 pm ET", 2: "Q2", 3: "Final"}[status],
                "gameDateEst": f"{g.date}T00:00:00Z",
                "gameDateTimeUTC": f"{g.date}T{tipoff_hour:02d}:30:00Z",
                "homeTeam_teamId": g.home,
                "awayTeam_teamId": g.away,
                "arenaName": "Fixture Arena",
                "postponedStatus": "N",
            }
            for g in games
        ]
    )


def scoreboard(games: list[FixtureGame], status: int, text: str, home: int, away: int):
    game_rows = pd.DataFrame(
        [{"gameId": g.id, "gameStatus": status, "gameStatusText": text} for g in games]
    )
    team_rows = pd.DataFrame(
        [
            {"gameId": g.id, "teamId": team, "score": score}
            for g in games
            for team, score in ((g.home, home), (g.away, away))
        ]
    )
    return [pd.DataFrame(), game_rows, team_rows]


@dataclass
class FakeSource:
    """Stands in for NBAStatsClient. Frames are keyed by (endpoint class name, P/T or None)."""

    frames: dict[tuple[str, str | None], pd.DataFrame] = field(default_factory=dict)
    calls: list[dict[str, Any]] = field(default_factory=list)
    error: Exception | None = None
    live_frames: list[pd.DataFrame] = field(default_factory=list)

    def fetch(self, endpoint_cls: type, *, cacheable: bool = False, **params: Any) -> FetchResult:
        self.calls.append({"endpoint": endpoint_cls.__name__, **params})
        if self.error:
            raise self.error
        if endpoint_cls.__name__ == "ScoreboardV3":
            return FetchResult(frames=self.live_frames, attempts=1)
        if endpoint_cls.__name__ == "BoxScoreMatchupsV3":
            frame = self.frames.get(("BoxScoreMatchupsV3", params["game_id"]), pd.DataFrame())
            return FetchResult(frames=[frame.copy()], attempts=1)
        key = (endpoint_cls.__name__, params.get("player_or_team_abbreviation"))
        return FetchResult(frames=[self.frames[key].copy()], attempts=1)

    def set_logs(self, games: list[FixtureGame], overrides=None) -> None:
        self.frames[("LeagueGameLog", "T")] = team_log(games)
        self.frames[("LeagueGameLog", "P")] = player_log(games, overrides)
