"""The four regression families compared on every target (model-methodology.md#models-compared)."""

from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

ALGORITHMS = ("rolling_baseline", "ridge", "random_forest", "xgboost")
BASELINE_WINDOW = 10


class Regressor(Protocol):
    def predict(self, X: pd.DataFrame) -> np.ndarray: ...


@dataclass(frozen=True)
class TrainConfig:
    seed: int = 20261028
    n_jobs: int = -1
    ridge_alphas: tuple[float, ...] = (0.1, 1.0, 10.0, 100.0, 1000.0)
    forest_grid: tuple[dict[str, Any], ...] = (
        {"max_depth": 12, "min_samples_leaf": 20},
        {"max_depth": 18, "min_samples_leaf": 20},
        {"max_depth": 18, "min_samples_leaf": 50},
    )
    forest_trees: int = 150
    xgb_trials: int = 8
    xgb_max_rounds: int = 3000
    xgb_early_stopping: int = 100
    extra: dict[str, Any] = field(default_factory=dict)


FAST_CONFIG = TrainConfig(
    ridge_alphas=(1.0, 10.0),
    forest_grid=({"max_depth": 6, "min_samples_leaf": 5},),
    forest_trees=20,
    xgb_trials=2,
    xgb_max_rounds=200,
    xgb_early_stopping=20,
    n_jobs=1,
)


class RollingBaseline:
    """Mean of the target over the player's previous 10 games (fewer when fewer exist)."""

    def __init__(self, target: str) -> None:
        self.target = target
        self.column = f"{target}_avg_{BASELINE_WINDOW}"

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return X[self.column].to_numpy(dtype=float)


@dataclass
class Fitted:
    algorithm: str
    model: Regressor
    params: dict[str, Any]
    validation_mae: float

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.maximum(0, self.model.predict(X))


def ridge(alpha: float) -> Any:
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=alpha))


def forest(params: dict[str, Any], config: TrainConfig) -> Any:
    return make_pipeline(
        SimpleImputer(strategy="median"),
        RandomForestRegressor(
            n_estimators=config.forest_trees,
            max_features=0.33,
            max_samples=0.5,
            random_state=config.seed,
            n_jobs=config.n_jobs,
            **params,
        ),
    )


def xgb_trials(config: TrainConfig) -> list[dict[str, Any]]:
    rng = np.random.default_rng(config.seed)
    return [
        {
            "learning_rate": float(rng.uniform(0.02, 0.1)),
            "max_depth": int(rng.integers(3, 9)),
            "subsample": float(rng.uniform(0.6, 1.0)),
            "colsample_bytree": float(rng.uniform(0.5, 1.0)),
            "min_child_weight": float(np.exp(rng.uniform(0, np.log(50)))),
        }
        for _ in range(config.xgb_trials)
    ]


def xgb(
    params: dict[str, Any], config: TrainConfig, rounds: int, early_stopping: bool
) -> XGBRegressor:
    return XGBRegressor(
        n_estimators=rounds,
        tree_method="hist",
        random_state=config.seed,
        n_jobs=config.n_jobs,
        early_stopping_rounds=config.xgb_early_stopping if early_stopping else None,
        **params,
    )


def _mae(model: Regressor, X: pd.DataFrame, y: np.ndarray) -> float:
    return float(mean_absolute_error(y, np.maximum(0, model.predict(X))))


def fit_select(
    algorithm: str,
    target: str,
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_val: pd.DataFrame,
    y_val: np.ndarray,
    config: TrainConfig,
) -> Fitted:
    """Fits every candidate on the training rows and keeps the lowest validation MAE."""
    candidates: list[tuple[dict[str, Any], Regressor]] = []
    if algorithm == "rolling_baseline":
        candidates.append(({"window": BASELINE_WINDOW}, RollingBaseline(target)))
    elif algorithm == "ridge":
        for alpha in config.ridge_alphas:
            candidates.append(({"alpha": alpha}, ridge(alpha).fit(X_train, y_train)))
    elif algorithm == "random_forest":
        for params in config.forest_grid:
            candidates.append((dict(params), forest(params, config).fit(X_train, y_train)))
    elif algorithm == "xgboost":
        for params in xgb_trials(config):
            model = xgb(params, config, config.xgb_max_rounds, early_stopping=True)
            model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
            candidates.append(({**params, "n_estimators": int(model.best_iteration) + 1}, model))
    else:
        raise ValueError(f"Unknown algorithm {algorithm}")
    scored = [(params, model, _mae(model, X_val, y_val)) for params, model in candidates]
    params, model, mae = min(scored, key=lambda c: c[2])
    return Fitted(algorithm=algorithm, model=model, params=params, validation_mae=mae)


def refit(
    fitted: Fitted, target: str, X: pd.DataFrame, y: np.ndarray, config: TrainConfig
) -> Fitted:
    """Same algorithm and hyperparameters, fitted on more data (no further tuning)."""
    params = dict(fitted.params)
    if fitted.algorithm == "rolling_baseline":
        model: Regressor = RollingBaseline(target)
    elif fitted.algorithm == "ridge":
        model = ridge(params["alpha"]).fit(X, y)
    elif fitted.algorithm == "random_forest":
        model = forest(params, config).fit(X, y)
    else:
        rounds = params.pop("n_estimators")
        model = xgb(params, config, rounds, early_stopping=False).fit(X, y, verbose=False)
    return Fitted(fitted.algorithm, model, fitted.params, fitted.validation_mae)
