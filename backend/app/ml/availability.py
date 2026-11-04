"""Who a team is missing tonight, measured by what those players have been producing.

A player's recent production comes from the team's earlier games only. Whether he plays tonight
is the one input from the target game: in training that is the box score, and at serving it is the
injury report, so a backtest knows absences a live forecast may not. Only rotation players count,
because a deep reserve sitting depends on how the game goes, which is exactly what a forecast must
not see. Definitions: docs/model-methodology.md#missing-players.
"""

import numpy as np
import pandas as pd

WINDOW_GAMES = 10
# Minutes per game played in the window that make someone a rotation player.
ROTATION_MINUTES = 15.0
ABSENCE_STATS = ("min", "pts", "reb", "ast", "fga")

TEAM_ABSENCE_FEATURES: tuple[str, ...] = tuple(f"absent_{s}" for s in ABSENCE_STATS)
OPP_ABSENCE_FEATURES: tuple[str, ...] = tuple(f"opp_absent_{s}" for s in ABSENCE_STATS)
ABSENCE_FEATURES: tuple[str, ...] = (*TEAM_ABSENCE_FEATURES, *OPP_ABSENCE_FEATURES)

_NAMES = {
    "min": "minutes",
    "pts": "points",
    "reb": "rebounds",
    "ast": "assists",
    "fga": "shot attempts",
}
ABSENCE_LABELS: dict[str, str] = {
    **{f"absent_{s}": f"Teammates' missing {n} per game" for s, n in _NAMES.items()},
    **{f"opp_absent_{s}": f"Opponent's missing {n} per game" for s, n in _NAMES.items()},
}


def _team_season(rows: pd.DataFrame) -> pd.DataFrame:
    """Absence totals for each game of one team's season, from a players-by-games grid."""
    games = rows[["game_date", "game_id"]].drop_duplicates().sort_values(["game_date", "game_id"])
    game_ids = games["game_id"].to_numpy()
    index = {g: i for i, g in enumerate(game_ids)}
    players = rows["player_id"].unique()
    position = {p: i for i, p in enumerate(players)}
    g = rows["game_id"].map(index).to_numpy()
    p = rows["player_id"].map(position).to_numpy()
    played = np.zeros((len(players), len(game_ids)), dtype=bool)
    played[p, g] = True
    grids = {}
    for stat in ABSENCE_STATS:
        grid = np.zeros_like(played, dtype=float)
        grid[p, g] = rows[stat].to_numpy(dtype=float)
        grids[stat] = grid

    out = {f"absent_{s}": np.zeros(len(game_ids)) for s in ABSENCE_STATS}
    for i in range(1, len(game_ids)):
        start = max(0, i - WINDOW_GAMES)
        appearances = played[:, start:i].sum(axis=1)
        window_minutes = grids["min"][:, start:i].sum(axis=1)
        per_appearance = np.divide(
            window_minutes, appearances, out=np.zeros_like(window_minutes), where=appearances > 0
        )
        missing = (per_appearance >= ROTATION_MINUTES) & ~played[:, i]
        for stat in ABSENCE_STATS:
            out[f"absent_{stat}"][i] = grids[stat][missing, start:i].sum() / (i - start)
    return pd.DataFrame({"game_id": game_ids, **out})


def team_absences(lines: pd.DataFrame) -> pd.DataFrame:
    """One row per team-game: the recent per-game production of rotation players who did not play.

    A player's total is spread over the whole window, so someone already out for several games
    counts less: his team's recent form has started to reflect it.
    """
    played = lines[lines["minutes"] > 0].assign(min=lambda d: d["minutes"].astype(float))
    columns = ["game_id", "team_id", *TEAM_ABSENCE_FEATURES]
    if played.empty:
        return pd.DataFrame(columns=columns)
    frames = [
        _team_season(rows).assign(team_id=team)
        for (team, _season), rows in played.groupby(["team_id", "season_id"], sort=False)
    ]
    return pd.concat(frames, ignore_index=True)[columns]


def expected_lines(
    lines: pd.DataFrame,
    *,
    game_id: str,
    game_date: pd.Timestamp,
    season_id: int,
    unavailable: set[tuple[int, int]],
) -> pd.DataFrame:
    """Earlier lines plus tonight's expected players, so serving reads absences just as training
    does. `unavailable` holds (player, team) pairs, since a traded player can sit for one team and
    play for another. Tonight's rows mark who plays; nothing reads their statistics as production.
    """
    if lines.empty:
        return lines
    tonight = lines[lines["season_id"] == season_id].drop_duplicates(["team_id", "player_id"])
    pairs = zip(tonight["player_id"], tonight["team_id"], strict=True)
    tonight = tonight[[pair not in unavailable for pair in pairs]].copy()
    tonight = tonight.assign(game_id=game_id, game_date=game_date, season_id=season_id, minutes=1.0)
    tonight[[s for s in ABSENCE_STATS if s != "min"]] = 0
    return pd.concat([lines, tonight], ignore_index=True)


def add_absences(df: pd.DataFrame, lines: pd.DataFrame) -> pd.DataFrame:
    """Join each target row's own team and opponent absences for its game."""
    absences = team_absences(lines)
    if absences.empty:
        return df.assign(**dict.fromkeys(ABSENCE_FEATURES, 0.0))
    opponent = absences.rename(
        columns={
            "team_id": "opponent_id",
            **{f"absent_{s}": f"opp_absent_{s}" for s in ABSENCE_STATS},
        }
    )
    joined = df.merge(absences, on=["game_id", "team_id"], how="left")
    joined = joined.merge(opponent, on=["game_id", "opponent_id"], how="left")
    joined[list(ABSENCE_FEATURES)] = joined[list(ABSENCE_FEATURES)].fillna(0.0)
    return joined
