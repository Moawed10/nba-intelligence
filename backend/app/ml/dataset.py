"""Training frame from PostgreSQL at a recorded data_version (docs/model-methodology.md)."""

from dataclasses import dataclass

import pandas as pd
from sqlalchemy import Engine, text

from app.db import current_data_version, session_scope
from app.ml.features import FEATURES, TARGETS, build_features, leakage_violations
from app.stats import double_double_flags

LINES_SQL = """
    SELECT s.game_id, g.game_date, g.season_id, g.season_type::text AS season_type, s.player_id,
           s.team_id,
           CASE WHEN g.home_team_id = s.team_id THEN g.away_team_id ELSE g.home_team_id END
             AS opponent_id,
           g.home_team_id = s.team_id AS is_home,
           s.minutes::float AS minutes, s.pts, s.reb, s.ast, s.fg3m, s.stl, s.blk, s.tov, s.fga,
           s.fg3a, s.fta
    FROM player_game_stats s JOIN games g ON g.id = s.game_id
    WHERE g.status = 'final'"""

TEAM_SQL = """
    SELECT t.game_id, g.game_date, g.season_id, t.team_id, t.pts, o.pts AS opp_pts, t.fga, t.oreb,
           t.tov, t.fta, t.minutes
    FROM team_game_stats t
    JOIN games g ON g.id = t.game_id
    JOIN team_game_stats o ON o.game_id = t.game_id AND o.team_id <> t.team_id
    WHERE g.status = 'final'"""

LABELS = (*TARGETS, "double_double")


@dataclass(frozen=True)
class Dataset:
    frame: pd.DataFrame
    data_version: int
    leakage_violations: int

    @property
    def eligible(self) -> pd.DataFrame:
        return self.frame[self.frame["eligible"]]


def load_history(engine: Engine) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    with session_scope(engine) as session:
        version = current_data_version(session) or 0
        connection = session.connection()
        lines = pd.read_sql(text(LINES_SQL), connection, parse_dates=["game_date"])
        teams = pd.read_sql(text(TEAM_SQL), connection, parse_dates=["game_date"])
    return lines, teams, version


def training_frame(lines: pd.DataFrame, team_games: pd.DataFrame) -> pd.DataFrame:
    """One row per player-game played: pregame features plus the observed outcomes."""
    played = lines[lines["minutes"] > 0].reset_index(drop=True)
    features = build_features(played, lines, team_games)
    outcomes = played[["season_type", "pts", "reb", "ast", "fg3m", "stl", "blk"]].copy()
    outcomes["min"] = played["minutes"]
    outcomes["double_double"] = double_double_flags(played).astype(int)
    return pd.concat([features, outcomes], axis=1)


def load_dataset(engine: Engine) -> Dataset:
    lines, teams, version = load_history(engine)
    frame = training_frame(lines, teams)
    return Dataset(frame=frame, data_version=version, leakage_violations=leakage_violations(frame))


__all__ = ["FEATURES", "LABELS", "Dataset", "load_dataset", "load_history", "training_frame"]
