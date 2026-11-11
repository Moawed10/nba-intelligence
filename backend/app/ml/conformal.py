"""Mondrian split-conformal intervals binned by predicted minutes or by the prediction itself
(model-methodology.md)."""

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
    binned_by: str = "predicted_minutes"

    @classmethod
    def fit(
        cls, residuals: np.ndarray, key: np.ndarray, alpha: float = ALPHA,
        binned_by: str = "predicted_minutes", bins: int = BINS,
    ) -> "MondrianConformal":  # fmt: skip
        edges = tuple(float(e) for e in np.quantile(key, np.linspace(0, 1, bins + 1)[1:-1]))
        groups = np.digitize(key, edges)
        quantiles, counts = [], []
        for b in range(bins):
            scores = np.sort(np.abs(residuals[groups == b]))
            n = len(scores)
            if n == 0:
                raise ValueError(f"Conformal bin {b} has no calibration observations")
            rank = min(n, math.ceil((n + 1) * (1 - alpha)))
            quantiles.append(float(scores[rank - 1]))
            counts.append(n)
        return cls(alpha=alpha, edges=edges, quantiles=tuple(quantiles), counts=tuple(counts),
                   binned_by=binned_by)  # fmt: skip

    def bins(self, key: np.ndarray) -> np.ndarray:
        return np.digitize(key, self.edges)

    def _key(self, prediction: np.ndarray, minutes: np.ndarray) -> np.ndarray:
        return prediction if self.binned_by == "prediction" else minutes

    def interval(
        self, prediction: np.ndarray, minutes: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        q = np.asarray(self.quantiles)[self.bins(self._key(prediction, minutes))]
        return np.maximum(0, prediction - q), prediction + q

    def coverage(self, y: np.ndarray, prediction: np.ndarray, minutes: np.ndarray) -> dict:
        lower, upper = self.interval(prediction, minutes)
        inside = (y >= lower) & (y <= upper)
        bins = self.bins(self._key(prediction, minutes))
        return {
            "level": 1 - self.alpha,
            "overall": float(inside.mean()),
            "by_bin": [
                {"bin": b, "n": int((bins == b).sum()), "coverage": float(inside[bins == b].mean())}
                for b in range(len(self.quantiles))
                if (bins == b).any()
            ],
            "mean_width": float((upper - lower).mean()),
        }

    def to_dict(self) -> dict:
        return {"method": "mondrian_split_conformal", **asdict(self)}

    @classmethod
    def from_dict(cls, data: dict) -> "MondrianConformal":
        return cls(
            alpha=data["alpha"],
            edges=tuple(data["edges"]),
            quantiles=tuple(data["quantiles"]),
            counts=tuple(data["counts"]),
            binned_by=data.get("binned_by", "predicted_minutes"),
        )
