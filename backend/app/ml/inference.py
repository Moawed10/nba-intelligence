"""Pregame inference with the active release (docs/model-methodology.md, Phase 7).

Features come from the same `build_features` used in training, over final games strictly before
the game date, so a served prediction sees exactly what a training row would have seen.
"""

import hashlib
import json
import math
import threading
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.ml.artifacts import load_artifact
from app.ml.conformal import MondrianConformal
from app.ml.dataset import LINES_SQL, TEAM_SQL
from app.ml.features import FEATURES, TARGETS, build_features
from app.models import ModelRelease, ModelVersion, ReleaseStatus

PLAYER_LINES_SQL = LINES_SQL + " AND s.player_id = :player_id AND g.game_date < :before"
# Both teams' recent games for rest, pace and defense, plus every team game the player appeared in
# (usage is relative to his team in that game, including former teams).
TEAMS_SQL = (
    TEAM_SQL
    + """ AND g.game_date < :before AND (
      t.team_id IN (:team_id, :opponent_id)
      OR (t.game_id, t.team_id) IN (
        SELECT game_id, team_id FROM player_game_stats WHERE player_id = :player_id))"""
)

# Inputs shown next to a forecast: the statistic's own recent form plus the shared context.
TEAM_TARGETS = ("team_pts", "home_win")

CONTEXT_INPUTS = (
    "season_games",
    "rest_days",
    "is_back_to_back",
    "is_home",
    "opp_def_rating_10",
    "opp_pace_10",
    "games_vs_opponent",
)


@dataclass(frozen=True)
class RegressionModel:
    model: Any
    conformal: MondrianConformal


@dataclass(frozen=True)
class ActiveRelease:
    id: uuid.UUID
    version: str
    feature_schema_version: str
    regressors: dict[str, RegressionModel]
    double_double: Any
    # Game score models ("team_pts" payload with conformal, "home_win" margin calibrator), if any.
    team: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Forecast:
    eligible: bool
    prior_games: int
    snapshot: dict[str, float | None]
    snapshot_sha256: str
    values: dict[str, tuple[float, float, float]]
    interval_level: float
    double_double_probability: float | None
    explanation: dict[str, Any]


_cache: dict[uuid.UUID, ActiveRelease] = {}
_lock = threading.Lock()


def active_release(session: Session, artifacts_dir: Path) -> ActiveRelease | None:
    """The active release with verified artifacts, loaded once per process; None if none is active.

    Raises ArtifactMismatch when stored bytes or the feature schema differ from the registry.
    """
    release = session.scalar(
        select(ModelRelease).where(ModelRelease.status == ReleaseStatus.active)
    )
    if release is None:
        return None
    with _lock:
        if release.id in _cache:
            return _cache[release.id]
        versions = session.scalars(
            select(ModelVersion).where(
                ModelVersion.release_id == release.id, ModelVersion.is_selected
            )
        ).all()
        regressors: dict[str, RegressionModel] = {}
        double_double = None
        team: dict[str, Any] = {}
        for v in versions:
            payload = load_artifact(artifacts_dir / v.artifact_path, v.artifact_sha256)
            if v.target.value == "double_double":
                double_double = payload["model"]
            elif v.target.value in TEAM_TARGETS:
                team[v.target.value] = payload
            else:
                conformal = MondrianConformal.from_dict(
                    v.interval_calibration or payload["conformal"]
                )
                regressors[v.target.value] = RegressionModel(payload["model"], conformal)
        missing = set(TARGETS) - set(regressors)
        if missing:
            raise LookupError(
                f"release {release.version} has no selected model for {sorted(missing)}"
            )
        loaded = ActiveRelease(
            release.id,
            release.version,
            release.feature_schema_version,
            regressors,
            double_double,
            team,
        )
        _cache[release.id] = loaded
        return loaded


def _value(x: Any) -> float | None:
    """Full precision: JSON floats round-trip exactly, so a snapshot reproduces its input."""
    v = float(x)
    return None if math.isnan(v) else v


def snapshot_hash(snapshot: dict[str, float | None]) -> str:
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


def pregame_features(
    session: Session,
    *,
    player_id: int,
    team_id: int,
    opponent_id: int,
    is_home: bool,
    game_id: str,
    game_date: date,
    season_id: int,
) -> pd.Series:
    connection = session.connection()
    params = {"player_id": player_id, "before": game_date}
    lines = pd.read_sql(
        text(PLAYER_LINES_SQL), connection, params=params, parse_dates=["game_date"]
    )
    teams = pd.read_sql(
        text(TEAMS_SQL),
        connection,
        params={**params, "team_id": team_id, "opponent_id": opponent_id},
        parse_dates=["game_date"],
    )
    if lines.empty:
        row = pd.Series({name: np.nan for name in FEATURES})
        row["prior_games"], row["eligible"] = 0, False
        return row
    target = pd.DataFrame(
        [
            {
                "game_id": game_id,
                "game_date": pd.Timestamp(game_date),
                "season_id": season_id,
                "player_id": player_id,
                "team_id": team_id,
                "opponent_id": opponent_id,
                "is_home": is_home,
            }
        ]
    )
    return build_features(target, lines, teams).iloc[0]


def predict(release: ActiveRelease, features: pd.Series) -> Forecast:
    snapshot = {name: _value(features[name]) for name in FEATURES}
    digest = snapshot_hash(snapshot)
    prior = int(features["prior_games"])
    if not bool(features["eligible"]):
        return Forecast(False, prior, snapshot, digest, {}, 0.0, None, {})

    # The model reads the snapshot itself, so a stored snapshot always reproduces its prediction.
    X = pd.DataFrame(
        [[np.nan if snapshot[n] is None else snapshot[n] for n in FEATURES]], columns=list(FEATURES)
    )
    minutes = np.maximum(0, release.regressors["min"].model.predict(X))
    values: dict[str, tuple[float, float, float]] = {}
    level = 0.0
    for target in TARGETS:
        regressor = release.regressors[target]
        point = np.maximum(0, regressor.model.predict(X))
        lower, upper = regressor.conformal.interval(point, minutes)
        values[target] = (float(point[0]), float(lower[0]), float(upper[0]))
        level = 1 - regressor.conformal.alpha

    probability = None
    if release.double_double is not None:
        probability = float(release.double_double.predict_proba(X)[:, 1][0])

    explanation = {
        "method": "inputs",
        "inputs": {
            target: {
                name: snapshot[name]
                for name in (
                    f"{target}_avg_5",
                    f"{target}_avg_10",
                    f"{target}_season_avg",
                    f"{target}_vs_opponent",
                )  # fmt: skip
            }
            for target in TARGETS
        },
        "context": {name: snapshot[name] for name in CONTEXT_INPUTS},
    }
    return Forecast(True, prior, snapshot, digest, values, level, probability, explanation)


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def activate(session: Session, version: str, artifacts_dir: Path, now: datetime) -> ModelRelease:
    """Make `version` the serving release after verifying every selected artifact; the previously
    active release is retired. Admin operation (CLI), never exposed over HTTP."""
    release = session.scalar(select(ModelRelease).where(ModelRelease.version == version))
    if release is None:
        raise LookupError(f"No release {version}")
    versions = session.scalars(
        select(ModelVersion).where(ModelVersion.release_id == release.id, ModelVersion.is_selected)
    ).all()
    targets = {v.target.value for v in versions}
    if not set(TARGETS) <= targets:
        raise LookupError(
            f"Release {version} has no selected model for {sorted(set(TARGETS) - targets)}"
        )
    for v in versions:
        load_artifact(artifacts_dir / v.artifact_path, v.artifact_sha256)
    for current in session.scalars(
        select(ModelRelease).where(ModelRelease.status == ReleaseStatus.active)
    ):
        if current.id != release.id:
            current.status = ReleaseStatus.retired
    session.flush()
    release.status = ReleaseStatus.active
    release.activated_at = now
    session.flush()
    clear_cache()
    return release
