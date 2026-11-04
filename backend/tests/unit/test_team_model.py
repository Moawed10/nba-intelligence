import numpy as np
import pandas as pd

from app.ml.team_model import OWN, TEAM_FEATURES, team_frame


def _games(seed: int = 3, n: int = 40) -> pd.DataFrame:
    """Two rows per game between four teams, one game per team per day."""
    rng = np.random.default_rng(seed)
    rows = []
    for day in range(n):
        for home, away in ((1, 2), (3, 4)) if day % 2 else ((1, 3), (2, 4)):
            gid = f"{day:04d}{home}{away}"
            pts = rng.integers(90, 130, size=2)
            for team, opp, is_home, mine, theirs in (
                (home, away, True, 0, 1),
                (away, home, False, 1, 0),
            ):
                rows.append({
                    "game_id": gid,
                    "game_date": pd.Timestamp("2099-10-20") + pd.Timedelta(days=day),
                    "season_id": 2099, "team_id": team, "opponent_id": opp, "is_home": is_home,
                    "pts": int(pts[mine]), "opp_pts": int(pts[theirs]), "fga": 88, "oreb": 10,
                    "tov": 13, "fta": 22, "minutes": 240, "opp_fga": 87, "opp_oreb": 9,
                    "opp_tov": 14, "opp_fta": 21,
                })  # fmt: skip
    return pd.DataFrame(rows)


NO_LINES = pd.DataFrame(
    columns=["game_id", "game_date", "season_id", "team_id", "player_id", "minutes"]
)


def test_a_games_own_result_never_reaches_its_features():
    games = _games()
    target = games["game_id"].iloc[-5]
    changed = games.copy()
    changed.loc[changed["game_id"] == target, ["pts", "opp_pts"]] += 40
    before = (
        team_frame(games, NO_LINES)
        .set_index(["game_id", "team_id"])
        .loc[target, list(TEAM_FEATURES)]
    )
    after = (
        team_frame(changed, NO_LINES)
        .set_index(["game_id", "team_id"])
        .loc[target, list(TEAM_FEATURES)]
    )
    pd.testing.assert_frame_equal(before, after)


def test_rows_pair_each_team_with_its_opponents_form():
    frame = team_frame(_games(), NO_LINES).set_index(["game_id", "team_id"])
    game = frame.index.get_level_values(0)[-1]
    rows = frame.loc[game]
    home, away = rows[rows["is_home"] == 1].iloc[0], rows[rows["is_home"] == 0].iloc[0]
    for name in (n for n in OWN if n != "season_games"):
        assert home[f"opp_{name}"] == away[name] or (
            np.isnan(home[f"opp_{name}"]) and np.isnan(away[name])
        )
