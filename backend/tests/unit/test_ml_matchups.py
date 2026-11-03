"""Defender features must only ever see earlier days (model-methodology.md#defender-matchups)."""

import numpy as np
import pandas as pd
import pytest

from app.ml.features import FEATURES, build_features, leakage_violations
from app.ml.matchups import (
    DEFENDER_PRIOR_POSSESSIONS,
    LEAGUE_PTS_PER_100,
    MATCHUP_FEATURES,
    OWN_RATE_PRIOR_POSSESSIONS,
    defender_features,
)
from tests.ml_fixtures import league, matchups

STAR, DEF_A, DEF_B, OTHER = 1, 101, 102, 2
TEAM_X, TEAM_Y = 50, 60


def _row(day, offense, defender, def_team, poss=10.0, pts=2, ast=1, fg3m=0, game=None):
    return {
        "game_id": game or f"g{day}",
        "game_date": pd.Timestamp("2090-01-01") + pd.Timedelta(days=day),
        "off_player_id": offense,
        "def_player_id": defender,
        "def_team_id": def_team,
        "poss": poss,
        "pts": pts,
        "ast": ast,
        "fg3m": fg3m,
        "off_position": "G",
    }


def _target(day, player=STAR, opponent=TEAM_X):
    return pd.DataFrame(
        [
            {
                "game_id": "target",
                "game_date": pd.Timestamp("2090-01-01") + pd.Timedelta(days=day),
                "player_id": player,
                "opponent_id": opponent,
            }
        ]
    )


def test_uses_only_the_defenders_now_on_the_opponent():
    rows = pd.DataFrame(
        [
            _row(0, STAR, DEF_A, TEAM_X, poss=30.0, pts=15),
            _row(1, STAR, DEF_B, TEAM_X, poss=10.0, pts=1),
            # DEF_B has since been traded, so he no longer counts as a likely defender.
            _row(2, OTHER, DEF_B, TEAM_Y, poss=5.0, pts=1),
        ]
    )
    out = defender_features(_target(3), rows).iloc[0]
    assert out["matchup_possessions"] == pytest.approx(30.0)
    assert out["likely_defender_share"] == pytest.approx(1.0)
    assert out["matchup_source_date"] == pd.Timestamp("2090-01-01")


def test_rates_are_shrunk_toward_the_players_usual_and_the_league():
    rows = pd.DataFrame(
        [
            _row(0, STAR, DEF_A, TEAM_X, poss=50.0, pts=20),
            _row(0, STAR, 103, TEAM_Y, poss=50.0, pts=10, game="g0b"),
        ]
    )
    out = defender_features(_target(1), rows).iloc[0]
    weight = 50.0 * 0.5 ** (1 / 365)
    usual = 30.0 / 100.0
    seen = (weight * 20 / 50 + OWN_RATE_PRIOR_POSSESSIONS * usual) / (
        weight + OWN_RATE_PRIOR_POSSESSIONS
    )
    assert out["pts_per100_edge_vs_likely"] == pytest.approx((seen - usual) * 100)
    allowed = (20 + DEFENDER_PRIOR_POSSESSIONS * LEAGUE_PTS_PER_100 / 100) / (
        50 + DEFENDER_PRIOR_POSSESSIONS
    )
    assert out["likely_defender_pts_allowed_per100"] == pytest.approx(allowed * 100)


def test_a_player_never_guarded_by_this_team_falls_back_to_the_position_rate():
    rows = pd.DataFrame([_row(0, OTHER, DEF_A, TEAM_X, poss=10.0, pts=3)])
    out = defender_features(_target(1), rows).iloc[0]
    assert out["matchup_possessions"] == 0
    assert np.isnan(out["pts_per100_edge_vs_likely"])
    assert out["opp_pts_allowed_to_position_per100"] == pytest.approx(30.0)
    assert out["likely_defender_pts_allowed_per100"] == pytest.approx(30.0)


def test_a_same_day_game_is_invisible():
    same_day = pd.DataFrame([_row(1, STAR, DEF_A, TEAM_X, poss=99.0, pts=50)])
    out = defender_features(_target(1), same_day).iloc[0]
    assert out["matchup_possessions"] == 0
    assert np.isnan(out["opp_pts_allowed_to_position_per100"])
    assert pd.isna(out["matchup_source_date"])


def test_changing_the_target_game_or_later_changes_no_feature():
    lines, teams = league()
    rows = matchups(lines)
    cutoff = pd.Timestamp(np.sort(lines["game_date"].unique())[40])
    tampered = rows.copy()
    later = tampered["game_date"] >= cutoff
    tampered.loc[later, ["pts", "ast", "fg3m"]] = 99
    tampered.loc[later, "poss"] = 1.0
    tampered.loc[later, "def_team_id"] = 3
    targets = lines[lines["game_date"] <= cutoff].reset_index(drop=True)
    pd.testing.assert_frame_equal(
        defender_features(targets, rows), defender_features(targets, tampered)
    )


def test_defender_sources_are_in_the_leakage_check():
    lines, teams = league()
    targets = lines[lines["minutes"] > 0].reset_index(drop=True)
    features = build_features(targets, lines, teams, matchups(lines))
    assert features["matchup_source_date"].notna().any()
    assert leakage_violations(features) == 0
    late = features.copy()
    late.loc[late.index[-1], "position_source_date"] = late["game_date"].iloc[-1]
    assert leakage_violations(late) == 1


def test_build_features_keeps_working_without_any_matchup_data():
    lines, teams = league()
    targets = lines.head(10).reset_index(drop=True)
    features = build_features(targets, lines, teams)
    assert list(features[list(MATCHUP_FEATURES)].columns) == list(MATCHUP_FEATURES)
    assert features[list(MATCHUP_FEATURES)].isna().all(axis=None)
    assert set(MATCHUP_FEATURES) <= set(FEATURES)
