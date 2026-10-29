"""Mondrian split-conformal intervals binned by predicted minutes (model-methodology.md)."""

import math
from dataclasses import asdict, dataclass

import numpy as np

ALPHA = 0.20
BINS = 3


@dataclass(frozen=True)
class MondrianConformal:
    alpha: float
    edges: tuple[float, ...]
    quantiles: tuple[float, ...]
    counts: tuple[int, ...]

    @classmethod
    def fit(
        cls, residuals: np.ndarray, minutes: np.ndarray, alpha: float = ALPHA
    ) -> "MondrianConformal":
        edges = tuple(float(e) for e in np.quantile(minutes, np.linspace(0, 1, BINS + 1)[1:-1]))
        bins = np.digitize(minutes, edges)
        quantiles, counts = [], []
        for b in range(BINS):
            scores = np.sort(np.abs(residuals[bins == b]))
            n = len(scores)
            if n == 0:
                raise ValueError(f"Conformal bin {b} has no calibration observations")
            rank = min(n, math.ceil((n + 1) * (1 - alpha)))
            quantiles.append(float(scores[rank - 1]))
            counts.append(n)
        return cls(alpha=alpha, edges=edges, quantiles=tuple(quantiles), counts=tuple(counts))

    def bins(self, minutes: np.ndarray) -> np.ndarray:
        return np.digitize(minutes, self.edges)

    def interval(
        self, prediction: np.ndarray, minutes: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        q = np.asarray(self.quantiles)[self.bins(minutes)]
        return np.maximum(0, prediction - q), prediction + q

    def coverage(self, y: np.ndarray, prediction: np.ndarray, minutes: np.ndarray) -> dict:
        lower, upper = self.interval(prediction, minutes)
        inside = (y >= lower) & (y <= upper)
        bins = self.bins(minutes)
        return {
            "level": 1 - self.alpha,
            "overall": float(inside.mean()),
            "by_bin": [
                {"bin": b, "n": int((bins == b).sum()), "coverage": float(inside[bins == b].mean())}
                for b in range(BINS)
                if (bins == b).any()
            ],
            "mean_width": float((upper - lower).mean()),
        }

    def to_dict(self) -> dict:
        return {
            "method": "mondrian_split_conformal",
            "binned_by": "predicted_minutes",
            **asdict(self),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MondrianConformal":
        return cls(
            alpha=data["alpha"],
            edges=tuple(data["edges"]),
            quantiles=tuple(data["quantiles"]),
            counts=tuple(data["counts"]),
        )
