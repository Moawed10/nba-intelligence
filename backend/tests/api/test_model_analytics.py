"""Backtests, model analytics and the prediction history explorer on the synthetic league.

The held-out models are the 10-game rolling baseline, so every backtest value can be checked
against the stored box scores, and every analytics number against the stored evaluations.
"""

from datetime import date

import pandas as pd
import pytest
from sklearn.dummy import DummyClassifier
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from app.ml.artifacts import save_artifact
from app.ml.backtest import run_backtest
from app.ml.features import FEATURES, TARGETS, feature_schema_version
from app.ml.models import RollingBaseline
from app.models import (
    Algorithm,
    ModelRelease,
    ModelTarget,
    ModelVersion,
    Prediction,
    PredictionKind,
    ReleaseStatus,
)
from tests.api.test_predictions import CONFORMAL, STAR, client, league  # noqa: F401

pytestmark = pytest.mark.integration

VERSION = "2099.11.10-7"


def _held_out_release(engine: Engine, directory) -> None:
    """A release whose test window is the fixture season, with persisted held-out models."""
    with Session(engine) as s, s.begin():
        release = ModelRelease(
            version=VERSION, feature_schema_version=feature_schema_version(),
            train_start=date(2090, 10, 1), train_end=date(2095, 6, 1), val_start=date(2095, 10, 1),
            val_end=date(2096, 6, 1), test_start=date(2099, 10, 1), test_end=date(2099, 11, 10),
            data_version=1, git_sha=None, status=ReleaseStatus.candidate,
        )  # fmt: skip
        s.add(release)
        s.flush()
        classifier = DummyClassifier(strategy="prior").fit(
            pd.DataFrame([[0.0] * len(FEATURES)] * 4, columns=list(FEATURES)), [0, 1, 1, 1]
        )
        for target in (*TARGETS, "double_double"):
            regression = target != "double_double"
            path = f"{VERSION}/held_out_{target}.joblib"
            model = RollingBaseline(target) if regression else classifier
            calibration = CONFORMAL.to_dict() if regression else None
            digest = save_artifact(directory / path, model, target=target, conformal=calibration)
            s.add(
                ModelVersion(
                    release_id=release.id,
                    target=ModelTarget(target),
                    algorithm=Algorithm.rolling_baseline if regression else Algorithm.logistic,
                    is_selected=False,
                    hyperparameters={"fit": "held_out"},
                    features=list(FEATURES),
                    interval_calibration=calibration,
                    artifact_path=path,
                    artifact_sha256=digest,
                    random_seed=0,
                )  # fmt: skip
            )


@pytest.fixture
def backtested(league: Engine, tmp_path) -> dict:  # noqa: F811
    _held_out_release(league, tmp_path)
    return run_backtest(league, tmp_path, VERSION)


def test_backtest_stores_scored_predictions_from_the_held_out_models(league, backtested):  # noqa: F811
    assert backtested["predictions"] > 0
    with league.connect() as conn:
        mismatches = conn.scalar(
            text(
                """
                SELECT count(*) FROM predictions p
                JOIN prediction_values v ON v.prediction_id = p.id AND v.stat = 'pts'
                JOIN prediction_evaluations e ON e.prediction_id = p.id AND e.stat = 'pts'
                JOIN player_game_stats s ON s.player_id = p.player_id AND s.game_id = p.game_id
                WHERE p.kind = 'backtest'
                  AND (e.actual <> s.pts OR abs(e.abs_error - abs(s.pts - v.point)) > 1e-9
                       OR v.point <> (p.feature_snapshot->>'pts_avg_10')::float)
                """
            )
        )
    assert mismatches == 0
    with Session(league) as s:
        kinds = s.scalars(select(Prediction.kind).distinct()).all()
        assert kinds == [PredictionKind.backtest]
        assert s.scalar(select(func.count()).select_from(Prediction)) == backtested["predictions"]


def test_a_release_is_backtested_only_once(league, tmp_path, backtested):  # noqa: F811
    with pytest.raises(RuntimeError, match="already has backtest predictions"):
        run_backtest(league, tmp_path, VERSION)


def test_analytics_summarise_exactly_the_stored_evaluations(league, client, backtested):  # noqa: F811
    body = client.get(f"/api/v1/models/{VERSION}/analytics?stat=pts").json()
    with league.connect() as conn:
        n, mae, covered = conn.execute(
            text(
                "SELECT count(*), avg(abs_error), avg(within_interval::int) "
                "FROM prediction_evaluations WHERE stat = 'pts'"
            )
        ).one()
    assert body["kind"] == "backtest" and body["algorithm"] == "rolling_baseline"
    assert body["n"] == n == backtested["predictions"]
    assert body["mae"] == pytest.approx(mae) and body["coverage"] == pytest.approx(float(covered))
    assert sum(p["n"] for p in body["calibration"]) == n
    assert sum(b["n"] for b in body["residuals"]) == n
    assert sum(b["n"] for b in body["coverage_by_bin"]) == n
    assert [b["minutes_to"] for b in body["coverage_by_bin"]] == [10.0, 20.0, None]


def test_pregame_analytics_are_empty_until_live_forecasts_are_scored(client, backtested):  # noqa: F811
    body = client.get(f"/api/v1/models/{VERSION}/analytics?stat=reb&kind=pregame").json()
    assert body["n"] == 0 and body["calibration"] == [] and body["mae"] is None


def test_history_lists_backtests_next_to_the_box_score(league, client, backtested):  # noqa: F811
    body = client.get(f"/api/v1/predictions/history?player_id={STAR}&kind=backtest").json()
    entries = body["entries"]
    assert entries and all(e["kind"] == "backtest" for e in entries)
    dates = [e["game_date"] for e in entries]
    assert dates == sorted(dates, reverse=True)
    with league.connect() as conn:
        actual = conn.scalar(
            text("SELECT pts FROM player_game_stats WHERE player_id = :p AND game_id = :g"),
            {"p": STAR, "g": entries[0]["game_id"]},
        )
    assert entries[0]["values"]["pts"]["actual"] == actual
    assert entries[0]["release_version"] == VERSION
    pregame = client.get(f"/api/v1/predictions/history?player_id={STAR}&kind=pregame").json()
    assert pregame["entries"] == []


def test_unknown_release_and_player_are_404(client, backtested):  # noqa: F811
    assert client.get("/api/v1/models/2099.01.01-1/analytics").status_code == 404
    assert client.get("/api/v1/predictions/history?player_id=424242").status_code == 404


def test_analytics_change_as_soon_as_a_result_is_scored(league, client, backtested):  # noqa: F811
    url = f"/api/v1/models/{VERSION}/analytics?stat=pts"
    before = client.get(url).json()["mae"]
    with league.begin() as conn:
        conn.execute(
            text(
                "UPDATE prediction_evaluations SET actual = actual + 100, abs_error = abs_error + 100, "
                "evaluated_at = now() + interval '1 minute' "
                "WHERE stat = 'pts' AND prediction_id = (SELECT prediction_id "
                "FROM prediction_evaluations WHERE stat = 'pts' LIMIT 1)"
            )
        )
    after = client.get(url).json()["mae"]
    assert after > before
