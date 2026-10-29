import numpy as np
import pytest

from app.ml import artifacts
from app.ml.artifacts import ArtifactMismatch, load_artifact, save_artifact
from app.ml.conformal import MondrianConformal
from app.ml.dataset import training_frame
from app.ml.features import FEATURES, TARGETS
from app.ml.models import ALGORITHMS, FAST_CONFIG
from app.ml.train import train_release
from app.stats import Line, double_double_flags, is_double_double
from tests.ml_fixtures import PLAN, league


@pytest.fixture(scope="module")
def frame():
    return training_frame(*league())


@pytest.fixture(scope="module")
def result(frame):
    return train_release(frame, FAST_CONFIG, PLAN)


def test_every_target_is_trained_with_every_family(result):
    assert set(result.targets) == set(TARGETS)
    for outcome in result.targets.values():
        assert set(outcome.evaluated) == set(ALGORITHMS)
        best = min(outcome.evaluated, key=lambda a: outcome.evaluated[a].validation_mae)
        assert outcome.selected == best
        for scores in outcome.scores.values():
            assert {"mae", "rmse", "r2", "n", "baseline_mae"} <= set(scores["test"])
            assert scores["test"]["n"] == len(result.splits.test)


def test_baseline_is_the_previous_ten_game_mean(result):
    test = result.splits.test
    baseline = result.targets["pts"].evaluated["rolling_baseline"]
    np.testing.assert_allclose(baseline.predict(test[list(FEATURES)]), test["pts_avg_10"])


def test_predictions_are_never_negative(result):
    X = result.splits.test[list(FEATURES)]
    for outcome in result.targets.values():
        assert (outcome.production.predict(X) >= 0).all()


def test_double_double_classifier_reports_calibration(result):
    dd = result.double_double
    assert dd.held_out.algorithm in ("logistic", "xgboost_classifier")
    probabilities = dd.held_out.predict_proba(result.splits.test[list(FEATURES)])
    assert ((probabilities >= 0) & (probabilities <= 1)).all()
    assert {"brier", "log_loss", "base_rate_brier", "reliability"} <= set(dd.test)


def test_retraining_is_reproducible(frame, result):
    again = train_release(frame, FAST_CONFIG, PLAN)
    for target, outcome in result.targets.items():
        for algorithm in ALGORITHMS:
            first = outcome.scores[algorithm]["test"]["mae"]
            second = again.targets[target].scores[algorithm]["test"]["mae"]
            tolerance = 1e-3 if algorithm == "xgboost" else 1e-6
            assert abs(first - second) <= tolerance, (target, algorithm)
    assert again.double_double.test["brier"] == pytest.approx(result.double_double.test["brier"])


def test_conformal_quantile_uses_the_finite_sample_rank():
    residuals = np.arange(1, 11, dtype=float)
    minutes = np.array([5, 6, 7, 20, 21, 22, 23, 35, 36, 37], dtype=float)
    conformal = MondrianConformal.fit(residuals, minutes, alpha=0.2)
    bins = conformal.bins(minutes)
    for b in range(3):
        scores = np.sort(residuals[bins == b])
        rank = min(len(scores), int(np.ceil((len(scores) + 1) * 0.8)))
        assert conformal.quantiles[b] == scores[rank - 1]
    lower, _ = conformal.interval(np.array([0.5]), np.array([5.0]))
    assert lower[0] == 0


def test_conformal_coverage_is_near_nominal_on_exchangeable_data():
    rng = np.random.default_rng(1)
    minutes = rng.uniform(5, 40, 6000)
    outcome = 50 + rng.normal(0, minutes / 10)
    prediction = np.full(6000, 50.0)
    conformal = MondrianConformal.fit(outcome[:3000] - prediction[:3000], minutes[:3000])
    coverage = conformal.coverage(outcome[3000:], prediction[3000:], minutes[3000:])
    assert 0.77 <= coverage["overall"] <= 0.83
    assert MondrianConformal.from_dict(conformal.to_dict()) == conformal


def test_vectorized_double_double_matches_the_scalar_definition(frame):
    sample = frame.head(500)
    for _, row in sample.iterrows():
        line = Line(game_date=row["game_date"].date(), minutes=row["min"], pts=row["pts"],
                    reb=row["reb"], ast=row["ast"], fg3m=row["fg3m"], stl=row["stl"],
                    blk=row["blk"], tov=0, oreb=0, dreb=0, pf=0, fgm=0, fga=0, fg3a=0, ftm=0,
                    fta=0)  # fmt: skip
        assert bool(row["double_double"]) == is_double_double(line)
    assert (double_double_flags(sample) == sample["double_double"].astype(bool)).all()


def test_artifacts_verify_bytes_and_feature_schema(tmp_path, monkeypatch):
    path = tmp_path / "model.joblib"
    digest = save_artifact(path, {"weights": [1, 2, 3]}, target="pts", algorithm="ridge")
    payload = load_artifact(path, digest)
    assert payload["model"] == {"weights": [1, 2, 3]}
    assert payload["features"] == list(FEATURES)

    with pytest.raises(ArtifactMismatch, match="SHA-256"):
        load_artifact(path, "0" * 64)
    monkeypatch.setattr(artifacts, "feature_schema_version", lambda: "different")
    with pytest.raises(ArtifactMismatch, match="feature schema"):
        load_artifact(path, digest)
