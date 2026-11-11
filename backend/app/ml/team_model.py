"""Game score model: each team's points from both teams' form before the game.

One row per team per final regular-season game. Every feature comes from that team's (or its
opponent's) earlier games only: windows are shifted by one game, so a row never sees its own result.
The win chance comes from the predicted margin, calibrated with a logistic fit on a later season.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sqlalchemy import Engine, text

from app.db import session_scope
from app.ml import metrics
from app.ml.availability import ABSENCE_FEATURES, add_absences
from app.ml.conformal import MondrianConformal
from app.ml.models import ALGORITHMS, Fitted, TrainConfig, fit_select, refit
from app.ml.splits import SplitPlan

TEAM_GAMES_SQL = """
    SELECT t.game_id, g.game_date, g.season_id, t.team_id, o.team_id AS opponent_id, t.is_home,
           t.pts, o.pts AS opp_pts, t.fga, t.oreb, t.tov, t.fta, t.minutes,
           o.fga AS opp_fga, o.oreb AS opp_oreb, o.tov AS opp_tov, o.fta AS opp_fta
    FROM team_game_stats t
    JOIN games g ON g.id = t.game_id
    JOIN team_game_stats o ON o.game_id = t.game_id AND o.team_id <> t.team_id
    WHERE g.status = 'final' AND g.season_type = 'regular'"""

OWN = (
    "pts_avg_5", "pts_avg_10", "pts_season_avg", "allowed_avg_10", "off_rating_10",
    "def_rating_10", "pace_10", "win_pct_season", "season_games", "rest_days",
)  # fmt: skip
TEAM_FEATURES: tuple[str, ...] = (
    *OWN,
    "is_home",
    *(f"opp_{name}" for name in OWN if name != "season_games"),
    *ABSENCE_FEATURES,
)
MIN_PRIOR_GAMES = 10
REST_CAP = 7


def _prior(df: pd.DataFrame, column: str, window: int, how: str = "sum") -> pd.Series:
    """Rolling `how` over the team's previous `window` games, excluding the current one."""
    return df.groupby("team_id", sort=False)[column].transform(
        lambda s: getattr(s.shift(1).rolling(window, min_periods=1), how)()
    )


def team_form(games: pd.DataFrame) -> pd.DataFrame:
    """Per team-game form from strictly earlier games of the same team."""
    df = games.sort_values(["team_id", "game_date", "game_id"], kind="mergesort").copy()
    df["poss"] = df["fga"] - df["oreb"] + df["tov"] + 0.44 * df["fta"]
    df["opp_poss"] = df["opp_fga"] - df["opp_oreb"] + df["opp_tov"] + 0.44 * df["opp_fta"]
    df["won"] = (df["pts"] > df["opp_pts"]).astype(float)
    df["pts_avg_5"] = _prior(df, "pts", 5, "mean")
    df["pts_avg_10"] = _prior(df, "pts", 10, "mean")
    df["allowed_avg_10"] = _prior(df, "opp_pts", 10, "mean")
    poss10 = _prior(df, "poss", 10)
    df["off_rating_10"] = _prior(df, "pts", 10) / poss10 * 100
    df["def_rating_10"] = _prior(df, "opp_pts", 10) / _prior(df, "opp_poss", 10) * 100
    df["pace_10"] = 48 * poss10 / (_prior(df, "minutes", 10) / 5)
    by_season = df.groupby(["team_id", "season_id"], sort=False)
    df["season_games"] = by_season.cumcount()
    df["pts_season_avg"] = by_season["pts"].transform(lambda s: s.shift(1).expanding().mean())
    df["win_pct_season"] = by_season["won"].transform(lambda s: s.shift(1).expanding().mean())
    gap = df.groupby("team_id", sort=False)["game_date"].diff().dt.days
    df["rest_days"] = (gap - 1).clip(lower=0, upper=REST_CAP).fillna(REST_CAP)
    df["prior_games"] = df.groupby("team_id", sort=False).cumcount()
    return df


def team_frame(games: pd.DataFrame, lines: pd.DataFrame) -> pd.DataFrame:
    """Training rows: each team-game with its own form, the opponent's form, who each side is
    missing (from player `lines`) and the outcome."""
    form = team_form(games)
    own = form[["game_id", "team_id", "opponent_id", "game_date", "season_id", "is_home", "pts",
                "prior_games", *OWN]].copy()  # fmt: skip
    opp = form[["game_id", "team_id", "prior_games", *[n for n in OWN if n != "season_games"]]]
    opp = opp.rename(columns={"team_id": "opponent_id", "prior_games": "opp_prior_games",
                              **{n: f"opp_{n}" for n in OWN}})  # fmt: skip
    frame = own.merge(opp, on=["game_id", "opponent_id"], how="inner")
    frame["is_home"] = frame["is_home"].astype(float)
    frame["eligible"] = (frame["prior_games"] >= MIN_PRIOR_GAMES) & (
        frame["opp_prior_games"] >= MIN_PRIOR_GAMES
    )
    frame = add_absences(frame, lines)
    return frame.sort_values(["game_date", "game_id", "is_home"]).reset_index(drop=True)


def load_team_games(engine: Engine) -> pd.DataFrame:
    with session_scope(engine) as session:
        return pd.read_sql(text(TEAM_GAMES_SQL), session.connection(), parse_dates=["game_date"])


@dataclass
class TeamOutcome:
    selected: str
    evaluated: dict[str, Fitted]
    scores: dict[str, dict[str, dict[str, float]]]
    conformal: MondrianConformal
    test_coverage: dict[str, Any]
    production: Fitted
    production_conformal: MondrianConformal
    win: dict[str, Any]
    production_win_model: LogisticRegression


def _margins(frame: pd.DataFrame, predicted: np.ndarray) -> pd.DataFrame:
    """Home margin per game from the two team rows: predicted margin and whether home won."""
    rows = frame[["game_id", "is_home", "pts"]].assign(pred=predicted)
    home = rows[rows["is_home"] == 1].set_index("game_id")
    away = rows[rows["is_home"] == 0].set_index("game_id")
    joined = home.join(away, lsuffix="_home", rsuffix="_away", how="inner")
    return pd.DataFrame(
        {
            "margin": joined["pred_home"] - joined["pred_away"],
            "home_won": (joined["pts_home"] > joined["pts_away"]).astype(int),
        }
    )


def _calibrator(margins: pd.DataFrame) -> LogisticRegression:
    return LogisticRegression().fit(margins[["margin"]].to_numpy(), margins["home_won"].to_numpy())


def train_team(frame: pd.DataFrame, config: TrainConfig, plan: SplitPlan) -> TeamOutcome:
    eligible = frame[frame["eligible"]]
    parts = {
        "train": eligible[eligible["season_id"].isin(plan.train)],
        "validation": eligible[eligible["season_id"] == plan.validation],
        "test": eligible[eligible["season_id"] == plan.test],
    }
    X = {k: v[list(TEAM_FEATURES)] for k, v in parts.items()}
    y = {k: v["pts"].to_numpy(dtype=float) for k, v in parts.items()}

    evaluated = {
        a: fit_select(a, "pts", X["train"], y["train"], X["validation"], y["validation"], config)
        for a in ALGORITHMS
    }
    scores = {
        a: {s: metrics.regression(y[s], f.predict(X[s])) for s in ("validation", "test")}
        for a, f in evaluated.items()
    }
    baseline_mae = scores["rolling_baseline"]["test"]["mae"]
    for s in scores.values():
        s["test"]["baseline_mae"] = baseline_mae
    selected = min(evaluated, key=lambda a: evaluated[a].validation_mae)
    chosen = evaluated[selected]

    val_pred, test_pred = chosen.predict(X["validation"]), chosen.predict(X["test"])
    conformal = MondrianConformal.fit(y["validation"] - val_pred, val_pred, binned_by="prediction")
    coverage = conformal.coverage(y["test"], test_pred, test_pred)

    win_model = _calibrator(_margins(parts["validation"], val_pred))
    test_margins = _margins(parts["test"], test_pred)
    p = win_model.predict_proba(test_margins[["margin"]].to_numpy())[:, 1]
    actual = test_margins["home_won"].to_numpy()
    home_rate = float(_margins(parts["train"], y["train"])["home_won"].mean())
    win = {
        "games": int(len(actual)),
        "brier": float(np.mean((p - actual) ** 2)),
        "accuracy": float(np.mean((p >= 0.5) == actual)),
        "baseline_accuracy": float(np.mean(actual == 1)),
        "baseline_brier": float(np.mean((home_rate - actual) ** 2)),
    }

    X_prod = pd.concat([X["train"], X["validation"]])
    y_prod = np.concatenate([y["train"], y["validation"]])
    production = refit(chosen, "pts", X_prod, y_prod, config)
    prod_test = production.predict(X["test"])
    return TeamOutcome(
        selected=selected,
        evaluated=evaluated,
        scores=scores,
        conformal=conformal,
        test_coverage=coverage,
        production=production,
        production_conformal=MondrianConformal.fit(
            y["test"] - prod_test, prod_test, binned_by="prediction"
        ),
        win=win,
        production_win_model=_calibrator(_margins(parts["test"], prod_test)),
    )
