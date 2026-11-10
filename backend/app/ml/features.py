"""Pregame features, shared unchanged by training and inference.

Every feature for a target game is joined "as of strictly before" its date (merge_asof with
allow_exact_matches=False), so no statistic from the target game or any later game can enter.
Definitions: docs/model-methodology.md#features.
"""

import hashlib
import json

import numpy as np
import pandas as pd

from app.ml.availability import ABSENCE_FEATURES, ABSENCE_LABELS, add_absences
from app.ml.matchups import MATCHUP_FEATURES, MATCHUP_LABELS, defender_features
from app.ml.matchups import SOURCE_DATES as MATCHUP_SOURCE_DATES
from app.stats import possessions, rest_days_from_gap

FEATURE_MODULE_VERSION = "3"
TARGETS = ("pts", "reb", "ast", "fg3m", "stl", "blk", "min")
VOLUME = ("fga", "fg3a", "fta")
WINDOWS = (3, 5, 10)
TREND_STATS = ("min", "fga", "pts")
SHRINK_GAMES = 3
MIN_PRIOR_GAMES = 5

TARGET_COLUMNS = (
    "game_id",
    "game_date",
    "season_id",
    "player_id",
    "team_id",
    "opponent_id",
    "is_home",
)

FEATURES: tuple[str, ...] = (
    *(f"{s}_avg_{n}" for s in (*TARGETS, *VOLUME) for n in WINDOWS),
    *(f"{s}_season_avg" for s in TARGETS),
    "season_games",
    *(f"{s}_trend" for s in TREND_STATS),
    "pts_std_10",
    "min_std_10",
    "usage_avg_10",
    "is_home",
    "rest_days",
    "is_back_to_back",
    "team_rest_days",
    "opp_def_rating_10",
    "opp_def_rating_season",
    "opp_pace_10",
    "team_pace_10",
    *(f"{s}_vs_opponent" for s in TARGETS),
    "games_vs_opponent",
    *MATCHUP_FEATURES,
    *ABSENCE_FEATURES,
)

# What a new release trains on. Defender features are left out: they did not improve validation
# error (docs/model-methodology.md#result-not-used).
TRAINING_FEATURES: tuple[str, ...] = tuple(f for f in FEATURES if f not in MATCHUP_FEATURES)

STAT_NAMES = {
    "pts": "Points",
    "reb": "Rebounds",
    "ast": "Assists",
    "fg3m": "3-pointers made",
    "stl": "Steals",
    "blk": "Blocks",
    "min": "Minutes",
    "fga": "Field-goal attempts",
    "fg3a": "3-point attempts",
    "fta": "Free-throw attempts",
}

FEATURE_LABELS: dict[str, str] = {
    **{
        f"{s}_avg_{n}": f"{STAT_NAMES[s]}, last {n} games"
        for s in (*TARGETS, *VOLUME)
        for n in WINDOWS
    },
    **{f"{s}_season_avg": f"{STAT_NAMES[s]}, season average" for s in TARGETS},
    "season_games": "Games played this season",
    **{f"{s}_trend": f"{STAT_NAMES[s]} trend (last 5 vs last 10)" for s in TREND_STATS},
    "pts_std_10": "Scoring variability, last 10 games",
    "min_std_10": "Minutes variability, last 10 games",
    "usage_avg_10": "Share of team possessions used, last 10 games",
    "is_home": "Home game",
    "rest_days": "Days of rest",
    "is_back_to_back": "Second night of a back-to-back",
    "team_rest_days": "Team days of rest",
    "opp_def_rating_10": "Opponent points allowed per 100 possessions, last 10",
    "opp_def_rating_season": "Opponent points allowed per 100 possessions, season",
    "opp_pace_10": "Opponent pace, last 10",
    "team_pace_10": "Team pace, last 10",
    **{f"{s}_vs_opponent": f"{STAT_NAMES[s]} against this opponent" for s in TARGETS},
    "games_vs_opponent": "Previous games against this opponent",
    **MATCHUP_LABELS,
    **ABSENCE_LABELS,
}

SOURCE_DATES = (
    "player_source_date",
    "team_source_date",
    "opp_source_date",
    "vs_source_date",
    *MATCHUP_SOURCE_DATES,
)


def feature_schema_version() -> str:
    payload = json.dumps({"version": FEATURE_MODULE_VERSION, "features": FEATURES})
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _played(lines: pd.DataFrame) -> pd.DataFrame:
    df = lines[lines["minutes"] > 0].copy()
    df["min"] = df["minutes"].astype(float)
    return df.sort_values(["player_id", "game_date", "game_id"], kind="mergesort")


def player_form(lines: pd.DataFrame, team_games: pd.DataFrame) -> pd.DataFrame:
    """Per player-game statistics including that game; joined to later games only."""
    df = _played(lines)
    team = team_games[["game_id", "team_id", "fga", "fta", "tov"]].rename(
        columns={"fga": "team_fga", "fta": "team_fta", "tov": "team_tov"}
    )
    df = df.merge(team, on=["game_id", "team_id"], how="left")
    team_usage = df["team_fga"] + 0.44 * df["team_fta"] + df["team_tov"]
    df["usage"] = (df["fga"] + 0.44 * df["fta"] + df["tov"]) / team_usage.where(team_usage > 0)

    by_player = df.groupby("player_id", sort=False)
    stats = [*TARGETS, *VOLUME]
    for n in WINDOWS:
        rolled = by_player[stats].rolling(n, min_periods=1).mean().reset_index(level=0, drop=True)
        for s in stats:
            df[f"{s}_avg_{n}"] = rolled[s]
    spread = by_player[["pts", "min"]].rolling(10, min_periods=2).std()
    spread = spread.reset_index(level=0, drop=True)
    df["pts_std_10"] = spread["pts"]
    df["min_std_10"] = spread["min"]
    usage = by_player["usage"].rolling(10, min_periods=1).mean()
    df["usage_avg_10"] = usage.reset_index(level=0, drop=True)

    by_season = df.groupby(["player_id", "season_id"], sort=False)
    df["season_games"] = by_season.cumcount() + 1
    for s in TARGETS:
        df[f"{s}_season_avg"] = by_season[s].cumsum() / df["season_games"]
    keep = [c for c in df.columns if c.endswith(("_avg_3", "_avg_5", "_avg_10", "_season_avg"))]
    keep += ["pts_std_10", "min_std_10"]
    return df[["player_id", "game_date", "season_id", "season_games", *keep]].rename(
        columns={"game_date": "player_source_date", "season_id": "source_season_id"}
    )


def opponent_history(lines: pd.DataFrame) -> pd.DataFrame:
    df = _played(lines)
    by_pair = df.groupby(["player_id", "opponent_id"], sort=False)
    out = df[["player_id", "opponent_id", "game_date"]].copy()
    out["games_vs_opponent"] = by_pair.cumcount() + 1
    for s in TARGETS:
        out[f"{s}_vs_sum"] = by_pair[s].cumsum()
    return out.rename(columns={"game_date": "vs_source_date"})


def team_form(team_games: pd.DataFrame) -> pd.DataFrame:
    """Per team-game rates including that game: defense, pace and last game date."""
    df = team_games.sort_values(["team_id", "game_date", "game_id"], kind="mergesort").copy()
    df["poss"] = possessions(df["fga"], df["oreb"], df["tov"], df["fta"])
    by_team = df.groupby("team_id", sort=False)
    rolled = by_team[["opp_pts", "poss", "minutes"]].rolling(10, min_periods=1).sum()
    rolled = rolled.reset_index(level=0, drop=True)
    df["def_rating_10"] = rolled["opp_pts"] / rolled["poss"] * 100
    df["pace_10"] = 48 * rolled["poss"] / (rolled["minutes"] / 5)
    by_season = df.groupby(["team_id", "season_id"], sort=False)
    df["def_rating_season"] = by_season["opp_pts"].cumsum() / by_season["poss"].cumsum() * 100
    return df[["team_id", "game_date", "def_rating_10", "def_rating_season", "pace_10"]]


def _asof(left: pd.DataFrame, right: pd.DataFrame, on: str, left_by, right_by) -> pd.DataFrame:
    return pd.merge_asof(
        left.sort_values("game_date", kind="mergesort"),
        right.sort_values(on, kind="mergesort"),
        left_on="game_date",
        right_on=on,
        left_by=left_by,
        right_by=right_by,
        allow_exact_matches=False,
        direction="backward",
    )


def build_features(
    targets: pd.DataFrame,
    lines: pd.DataFrame,
    team_games: pd.DataFrame,
    matchups: pd.DataFrame | None = None,
    team_lines: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Features for each target row (a player in a game) from history strictly before its date,
    plus who plays in that game (`team_lines`, by default `lines`; see app/ml/availability.py).

    Returns one row per target, in the targets' order, with FEATURES, `prior_games` (games in the
    current and previous season), `eligible`, and the source date of every joined history.
    """
    base = targets[list(TARGET_COLUMNS)].copy()
    base["_row"] = np.arange(len(base))
    base["game_date"] = pd.to_datetime(base["game_date"])
    lines = lines.assign(game_date=pd.to_datetime(lines["game_date"]))
    team_games = team_games.assign(game_date=pd.to_datetime(team_games["game_date"]))

    df = _asof(base, player_form(lines, team_games), "player_source_date", "player_id", "player_id")
    same_season = df["source_season_id"] == df["season_id"]
    df["season_games"] = df["season_games"].where(same_season, 0).fillna(0)

    per_season = _played(lines).groupby(["player_id", "season_id"]).size()
    prev = per_season.rename("prev_season_games").reset_index()
    prev["season_id"] = prev["season_id"] + 1
    df = df.merge(prev, on=["player_id", "season_id"], how="left")
    df["prior_games"] = df["season_games"] + df["prev_season_games"].fillna(0)
    df["eligible"] = df["prior_games"] >= MIN_PRIOR_GAMES

    for s in TREND_STATS:
        df[f"{s}_trend"] = df[f"{s}_avg_5"] - df[f"{s}_avg_10"]
    df["rest_days"] = rest_days_from_gap((df["game_date"] - df["player_source_date"]).dt.days)
    df["is_home"] = df["is_home"].astype(float)

    teams = team_form(team_games)
    own = teams.rename(columns={"game_date": "team_source_date", "pace_10": "team_pace_10"})
    own = own[["team_id", "team_source_date", "team_pace_10"]]
    df = _asof(df, own, "team_source_date", "team_id", "team_id")
    team_gap = (df["game_date"] - df["team_source_date"]).dt.days
    df["team_rest_days"] = rest_days_from_gap(team_gap)
    df["is_back_to_back"] = (team_gap == 1).astype(float)

    opp = teams.rename(
        columns={
            "game_date": "opp_source_date",
            "team_id": "opp_team_id",
            "def_rating_10": "opp_def_rating_10",
            "def_rating_season": "opp_def_rating_season",
            "pace_10": "opp_pace_10",
        }
    )
    df = _asof(df, opp, "opp_source_date", "opponent_id", "opp_team_id").drop(columns="opp_team_id")

    pair = ["player_id", "opponent_id"]
    df = _asof(df, opponent_history(lines), "vs_source_date", pair, pair)
    n = df["games_vs_opponent"].fillna(0)
    df["games_vs_opponent"] = n
    weight = n / (n + SHRINK_GAMES)
    for s in TARGETS:
        vs_avg = (df[f"{s}_vs_sum"] / n.where(n > 0)).fillna(0)
        df[f"{s}_vs_opponent"] = weight * vs_avg + (1 - weight) * df[f"{s}_season_avg"]

    df = add_absences(df, lines if team_lines is None else team_lines)
    df = df.sort_values("_row").reset_index(drop=True)
    guarded = defender_features(base, matchups)
    df = pd.concat([df, guarded.reset_index(drop=True)], axis=1)
    identity = [c for c in TARGET_COLUMNS if c not in FEATURES]
    return df[[*identity, *FEATURES, "prior_games", "eligible", *SOURCE_DATES]]


def leakage_violations(features: pd.DataFrame) -> int:
    """Rows whose features came from a game on or after the target game's date."""
    late = pd.Series(False, index=features.index)
    for column in SOURCE_DATES:
        late |= features[column].notna() & (features[column] >= features["game_date"])
    return int(late.sum())
