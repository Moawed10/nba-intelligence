"""Double-double probability: direct classifier with isotonic calibration."""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from app.ml.models import TrainConfig

CLASSIFIERS = ("logistic", "xgboost_classifier")


def _make(algorithm: str, config: TrainConfig) -> Any:
    if algorithm == "logistic":
        return make_pipeline(
            SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(max_iter=2000)
        )
    return XGBClassifier(
        n_estimators=min(400, config.xgb_max_rounds),
        learning_rate=0.05,
        max_depth=5,
        subsample=0.8,
        colsample_bytree=0.8,
        tree_method="hist",
        random_state=config.seed,
        n_jobs=config.n_jobs,
        eval_metric="logloss",
    )


@dataclass
class CalibratedClassifier:
    algorithm: str
    model: Any
    raw_validation_log_loss: dict[str, float]

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(X)[:, 1]


def fit_classifier(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_cal: pd.DataFrame,
    y_cal: np.ndarray,
    config: TrainConfig,
    algorithm: str | None = None,
) -> CalibratedClassifier:
    """Picks the algorithm by raw log loss on the calibration season, then fits isotonic
    calibration on that season. Pass `algorithm` to refit a chosen one without re-selecting."""
    fitted = {
        a: _make(a, config).fit(X_train, y_train)
        for a in ([algorithm] if algorithm else CLASSIFIERS)
    }
    losses = {a: float(log_loss(y_cal, m.predict_proba(X_cal)[:, 1])) for a, m in fitted.items()}
    chosen = algorithm or min(losses, key=losses.get)
    calibrated = CalibratedClassifierCV(FrozenEstimator(fitted[chosen]), method="isotonic")
    calibrated.fit(X_cal, y_cal)
    return CalibratedClassifier(algorithm=chosen, model=calibrated, raw_validation_log_loss=losses)
