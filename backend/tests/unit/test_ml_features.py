"""Leakage gates for the feature pipeline (model-methodology.md, "Leakage tests")."""

import numpy as np
import pandas as pd
import pytest

from app.ml.dataset import training_frame
from app.ml.features import (
    FEATURES,
    MIN_PRIOR_GAMES,
    build_features,
    feature_schema_version,
    leakage_violations,
)
from app.ml.matchups import MATCHUP_FEATURES
from app.ml.splits import SplitPlan, split
from tests.ml_fixtures import PLAN, league

PLAYER = 10
STAT_COLUMNS = ("pts", "reb", "ast", "fg3m", "stl", "blk", "tov", "fga", "fg3a", "fta")
TEAM_COLUMNS = ("pts", "opp_pts", "fga", "oreb", "tov", "fta")


@pytest.fixture(scope="module")
def history():
    return league()


@pytest.fixture(scope="module")
def frame(history):
    return training_frame(*history)


def test_rolling_features_equal_independent_means_of_previous_games(history):
    lines, teams = history
    games = lines[lines["player_id"] == PLAYER].sort_values("game_date").head(12)
    features = build_features(games.reset_index(drop=True), lines, teams)
    pts = games["pts"].to_numpy(float)
    for k in range(1, 12):
        for n in (3, 5, 10):
            expected = pts[max(0, k - n) : k].mean()
            assert features.loc[k, f"pts_avg_{n}"] == pytest.approx(expected), (k, n)
    assert np.isnan(features.loc[0, "pts_avg_3"])


def test_features_ignore_the_target_game_and_everything_after_it(history):
    lines, teams = history
    cutoff = pd.Timestamp(np.sort(lines["game_date"].unique())[40])
    perturbed = lines.copy()
    later = perturbed["game_date"] >= cutoff
    for column in STAT_COLUMNS:
        perturbed.loc[later, column] = perturbed.loc[later, column] * 3 + 7
    perturbed.loc[later, "minutes"] = 1.0
    perturbed_teams = teams.copy()
    team_later = perturbed_teams["game_date"] >= cutoff
    for column in TEAM_COLUMNS:
        perturbed_teams.loc[team_later, column] = perturbed_teams.loc[team_later, column] * 2 + 50

    targets = lines[(lines["game_date"] <= cutoff) & (lines["minutes"] > 0)].reset_index(drop=True)
    original = build_features(targets, lines, teams)
    changed = build_features(targets, perturbed, perturbed_teams)
    assert (targets["game_date"] == cutoff).any()
    pd.testing.assert_frame_equal(original[list(FEATURES)], changed[list(FEATURES)])


def test_every_joined_history_predates_its_target_game(frame):
    assert leakage_violations(frame) == 0
    eligible = frame[frame["eligible"]]
    for column in ("player_source_date", "team_source_date", "opp_source_date"):
        assert (eligible[column] < eligible["game_date"]).all(), column
    seen = eligible["vs_source_date"].dropna()
    assert (seen < eligible.loc[seen.index, "game_date"]).all()


def test_leakage_check_detects_a_same_day_source(frame):
    tampered = frame.copy()
    row = tampered.index[50]
    tampered.loc[row, "opp_source_date"] = tampered.loc[row, "game_date"]
    assert leakage_violations(tampered) == 1


def test_eligibility_requires_prior_games(frame):
    assert (frame.loc[frame["eligible"], "prior_games"] >= MIN_PRIOR_GAMES).all()
    assert not frame.loc[frame["prior_games"] < MIN_PRIOR_GAMES, "eligible"].any()
    # Defender history is optional: a player may never have met this opponent.
    always = [f for f in FEATURES if f not in MATCHUP_FEATURES]
    assert frame.loc[frame["eligible"], always].notna().all().all()


def test_first_game_of_a_season_falls_back_to_the_previous_season(history, frame):
    lines, _ = history
    second_season = frame[(frame["player_id"] == PLAYER) & (frame["season_id"] == 2091)]
    opener = second_season.sort_values("game_date").iloc[0]
    previous = lines[(lines["player_id"] == PLAYER) & (lines["season_id"] == 2090)]
    assert opener["season_games"] == 0
    assert opener["pts_season_avg"] == pytest.approx(previous["pts"].mean())


def test_back_to_back_and_rest_come_from_schedule_dates(frame):
    eligible = frame[frame["eligible"]]
    gap = (eligible["game_date"] - eligible["team_source_date"]).dt.days
    assert ((gap == 1) == (eligible["is_back_to_back"] == 1)).all()
    assert (gap == 1).any()
    assert eligible["rest_days"].between(0, 7).all()


def test_splits_are_chronological_and_disjoint(frame):
    parts = split(frame, PLAN)
    assert parts.chronological
    assert parts.train["game_date"].max() < parts.validation["game_date"].min()
    assert parts.validation["game_date"].max() < parts.test["game_date"].min()
    with pytest.raises(ValueError, match="overlap"):
        split(frame, SplitPlan(train=(2090, 2092), validation=2091, test=2093))


def test_schema_version_is_stable_and_tracks_feature_names(monkeypatch):
    first = feature_schema_version()
    assert first == feature_schema_version()
    monkeypatch.setattr("app.ml.features.FEATURES", (*FEATURES, "extra"))
    assert feature_schema_version() != first
