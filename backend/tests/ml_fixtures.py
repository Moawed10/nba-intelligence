"""Synthetic league for ML tests: invented seasons 2090-2093, 4 teams, 5 players each.

Every value is generated from a fixed seed, so nothing here can be mistaken for NBA data.
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.ml.splits import SplitPlan

SEASONS = (2090, 2091, 2092, 2093)
PLAN = SplitPlan(train=(2090, 2091), validation=2092, test=2093)
TEAMS = (1, 2, 3, 4)
ROUNDS = (((1, 2), (3, 4)), ((1, 3), (2, 4)), ((1, 4), (2, 3)))
GAME_DAYS = 18
TOTALS = ("pts", "fga", "oreb", "tov", "fta")


def _player_line(rng, skill: float, slot: int) -> dict:
    minutes = float(np.clip(rng.normal(30 - slot * 2, 4), 4, 44))
    pts = int(max(0, rng.normal(skill * minutes / 30, 4)))
    return {
        "minutes": minutes,
        "pts": pts,
        "reb": int(rng.poisson(3 + slot)),
        "ast": int(rng.poisson(5 - slot * 0.8)),
        "fg3m": int(rng.poisson(1.5)),
        "stl": int(rng.poisson(1)),
        "blk": int(rng.poisson(0.6)),
        "tov": int(rng.poisson(2)),
        "fga": max(pts // 2, 1),
        "fg3a": int(rng.poisson(4)),
        "fta": int(rng.poisson(3)),
        "oreb": int(rng.poisson(1)),
    }


def league(seed: int = 7) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    skill = {team * 10 + slot: rng.uniform(4, 26) for team in TEAMS for slot in range(5)}
    lines, team_rows = [], []
    for season in SEASONS:
        start = date(season, 10, 20)
        for day in range(GAME_DAYS):
            game_date = pd.Timestamp(start + timedelta(days=2 * day + (day % 3 == 0)))
            for pair, (home, away) in enumerate(ROUNDS[day % 3]):
                game_id = f"{season % 100:02d}{day:03d}{pair}"
                game = {"game_id": game_id, "game_date": game_date, "season_id": season}
                totals = {}
                for team, opponent in ((home, away), (away, home)):
                    rows = [
                        {
                            **game,
                            "season_type": "regular",
                            "player_id": team * 10 + slot,
                            "team_id": team,
                            "opponent_id": opponent,
                            "is_home": team == home,
                            **_player_line(rng, skill[team * 10 + slot], slot),
                        }
                        for slot in range(5)
                    ]
                    lines += rows
                    totals[team] = {k: sum(r[k] for r in rows) for k in TOTALS}
                for team, opponent in ((home, away), (away, home)):
                    team_rows.append(
                        {
                            **game,
                            "team_id": team,
                            **totals[team],
                            "opp_pts": totals[opponent]["pts"],
                            "minutes": 240,
                        }  # fmt: skip
                    )
    return pd.DataFrame(lines), pd.DataFrame(team_rows)
