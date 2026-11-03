"""Backtest predictions for a release's held-out test season (docs/model-methodology.md).

The models used are the release's held-out versions: fitted on the training seasons only, chosen on
the validation season, with intervals calibrated on the validation season. None of them saw the
test season, so these predictions are what the release would have said before each test game.
They are stored with kind "backtest" and scored against the box scores; live pregame forecasts
stay separate.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import Engine, exists, insert, select

from app.db import session_scope
from app.ml.artifacts import load_artifact
from app.ml.conformal import MondrianConformal
from app.ml.dataset import load_dataset
from app.ml.features import TARGETS
from app.ml.inference import snapshot_hash
from app.models import (
    ModelRelease,
    ModelVersion,
    Prediction,
    PredictionEvaluation,
    PredictionKind,
    PredictionStatus,
    PredictionValue,
)

CHUNK = 2000
LEVEL = Decimal("0.80")


def _held_out(session, release: ModelRelease) -> dict[str, dict[str, Any]]:
    """The chosen held-out model per target (the only held-out versions with an artifact)."""
    return {
        v.target.value: {"version": v}
        for v in session.scalars(
            select(ModelVersion).where(
                ModelVersion.release_id == release.id,
                ModelVersion.hyperparameters["fit"].astext == "held_out",
                ModelVersion.artifact_sha256 != "",
            )
        )
    }


def run_backtest(
    engine: Engine, artifacts_dir: Path, version: str, now: datetime | None = None
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    with session_scope(engine) as session:
        release = session.scalar(select(ModelRelease).where(ModelRelease.version == version))
        if release is None:
            raise LookupError(f"no release {version}")
        if session.scalar(
            select(
                exists().where(
                    Prediction.release_id == release.id, Prediction.kind == PredictionKind.backtest
                )
            )
        ):
            raise RuntimeError(f"release {version} already has backtest predictions")
        models = _held_out(session, release)
        missing = {*TARGETS, "double_double"} - set(models)
        if missing:
            raise LookupError(f"release {version} has no held-out model for {sorted(missing)}")
        for entry in models.values():
            v = entry["version"]
            payload = load_artifact(
                artifacts_dir / v.artifact_path, v.artifact_sha256, release.feature_schema_version
            )
            entry["model"] = payload["model"]
            features = list(payload["features"])
            calibration = v.interval_calibration or payload.get("conformal")
            entry["conformal"] = MondrianConformal.from_dict(calibration) if calibration else None
        release_id, schema = release.id, release.feature_schema_version
        test_start, test_end = release.test_start, release.test_end

    frame = load_dataset(engine).eligible
    dates = frame["game_date"].dt.date
    rows = frame[(dates >= test_start) & (dates <= test_end)].reset_index(drop=True)
    if rows.empty:
        raise RuntimeError(f"no eligible games between {test_start} and {test_end}")
    X = rows[features].astype(float)
    minutes = np.maximum(0, models["min"]["model"].predict(X))
    predicted: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for target in TARGETS:
        point = np.maximum(0, models[target]["model"].predict(X))
        lower, upper = models[target]["conformal"].interval(point, minutes)
        predicted[target] = (point, lower, upper)
    probability = models["double_double"]["model"].predict_proba(X)[:, 1]

    ids = [uuid.uuid4() for _ in range(len(rows))]
    predictions, values, evaluations = [], [], []
    for i, row in rows.iterrows():
        snapshot = {n: None if pd.isna(row[n]) else float(row[n]) for n in features}
        cutoff = row["game_date"].to_pydatetime().replace(tzinfo=UTC)
        predictions.append({
            "id": ids[i], "player_id": int(row["player_id"]), "game_id": row["game_id"],
            "release_id": release_id, "kind": PredictionKind.backtest,
            "status": PredictionStatus.ok, "feature_schema_version": schema,
            "feature_snapshot": snapshot, "feature_snapshot_sha256": snapshot_hash(snapshot),
            "explanation": None, "data_cutoff_at": cutoff,
            "created_at": now, "double_double_probability": float(probability[i]),
        })  # fmt: skip
        for target in TARGETS:
            point, lower, upper = (float(a[i]) for a in predicted[target])
            actual = float(row[target])
            values.append({"prediction_id": ids[i], "stat": target, "point": point,
                           "lower": lower, "upper": upper, "interval_level": LEVEL})  # fmt: skip
            evaluations.append({"prediction_id": ids[i], "stat": target, "actual": actual,
                                "abs_error": abs(actual - point),
                                "within_interval": lower <= actual <= upper,
                                "evaluated_at": now})  # fmt: skip
        actual_dd = float(row["double_double"])
        evaluations.append({"prediction_id": ids[i], "stat": "double_double", "actual": actual_dd,
                            "abs_error": abs(actual_dd - float(probability[i])),
                            "within_interval": None, "evaluated_at": now})  # fmt: skip

    with session_scope(engine) as session:
        for table, batch in ((Prediction, predictions), (PredictionValue, values),
                             (PredictionEvaluation, evaluations)):  # fmt: skip
            for start in range(0, len(batch), CHUNK):
                session.execute(insert(table), batch[start : start + CHUNK])
        session.commit()
    return {
        "release": version,
        "predictions": len(predictions),
        "games": int(rows["game_id"].nunique()),
        "from": str(test_start),
        "to": str(test_end),
    }
