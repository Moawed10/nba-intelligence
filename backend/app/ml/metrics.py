import numpy as np
from sklearn.metrics import (
    brier_score_loss,
    log_loss,
    mean_absolute_error,
    r2_score,
    root_mean_squared_error,
)


def regression(y: np.ndarray, prediction: np.ndarray) -> dict[str, float]:
    return {
        "n": int(len(y)),
        "mae": float(mean_absolute_error(y, prediction)),
        "rmse": float(root_mean_squared_error(y, prediction)),
        "r2": float(r2_score(y, prediction)),
    }


def reliability(y: np.ndarray, probability: np.ndarray, bins: int = 10) -> list[dict[str, float]]:
    edges = np.linspace(0, 1, bins + 1)
    index = np.clip(np.digitize(probability, edges[1:-1]), 0, bins - 1)
    rows = []
    for b in range(bins):
        mask = index == b
        if mask.any():
            rows.append(
                {
                    "bin_low": float(edges[b]),
                    "bin_high": float(edges[b + 1]),
                    "n": int(mask.sum()),
                    "mean_predicted": float(probability[mask].mean()),
                    "observed_rate": float(y[mask].mean()),
                }
            )
    return rows


def classification(y: np.ndarray, probability: np.ndarray) -> dict[str, object]:
    base_rate = float(y.mean())
    return {
        "n": int(len(y)),
        "brier": float(brier_score_loss(y, probability)),
        "log_loss": float(log_loss(y, probability, labels=[0, 1])),
        "base_rate": base_rate,
        "base_rate_brier": float(brier_score_loss(y, np.full(len(y), base_rate))),
        "reliability": reliability(y, probability),
    }
