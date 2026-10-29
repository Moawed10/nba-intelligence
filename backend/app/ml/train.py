"""Training run: compare models per target on chronological splits, calibrate, persist, register.

Reported metrics come from the held-out fit (train seasons, selection on validation, reported on
test). The production model per target refits the selected configuration on train + validation
and calibrates its intervals on the test season. See docs/model-methodology.md.
"""

import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import Engine, func, select

from app.db import session_scope
from app.ml import metrics
from app.ml.artifacts import library_versions, save_artifact
from app.ml.classifier import CalibratedClassifier, fit_classifier
from app.ml.conformal import MondrianConformal
from app.ml.dataset import load_dataset
from app.ml.features import FEATURES, TARGETS, feature_schema_version
from app.ml.models import ALGORITHMS, Fitted, TrainConfig, fit_select, refit
from app.ml.splits import DEFAULT_PLAN, SplitPlan, Splits, split
from app.ml.team_model import TEAM_FEATURES, TeamOutcome, load_team_games, team_frame, train_team
from app.models import (
    Algorithm,
    EvaluationSplit,
    ModelEvaluation,
    ModelRelease,
    ModelTarget,
    ModelVersion,
    ReleaseStatus,
)

log = logging.getLogger(__name__)
NOT_PERSISTED = "not persisted"


@dataclass
class TargetOutcome:
    target: str
    evaluated: dict[str, Fitted]
    scores: dict[str, dict[str, Any]]
    selected: str
    conformal: MondrianConformal
    test_coverage: dict[str, Any]
    production: Fitted
    production_conformal: MondrianConformal


@dataclass
class ClassifierOutcome:
    held_out: CalibratedClassifier
    validation: dict[str, Any]
    test: dict[str, Any]
    production: CalibratedClassifier


@dataclass
class TrainingResult:
    plan: SplitPlan
    splits: Splits
    config: TrainConfig
    targets: dict[str, TargetOutcome] = field(default_factory=dict)
    double_double: ClassifierOutcome | None = None
    team: TeamOutcome | None = None
    seconds: float = 0.0


def _slices(frame: pd.DataFrame, y: np.ndarray, prediction: np.ndarray) -> dict[str, Any]:
    scores = metrics.regression(y, prediction)
    scores["by_season_type"] = {
        kind: metrics.regression(y[mask], prediction[mask])
        for kind in sorted(frame["season_type"].unique())
        if (mask := (frame["season_type"] == kind).to_numpy()).sum() > 1
    }
    return scores


def train_release(
    frame: pd.DataFrame,
    config: TrainConfig,
    plan: SplitPlan = DEFAULT_PLAN,
    targets: tuple[str, ...] = TARGETS,
    classify: bool = True,
) -> TrainingResult:
    started = time.perf_counter()
    parts = split(frame, plan)
    result = TrainingResult(plan=plan, splits=parts, config=config)
    X_train, X_val, X_test = (
        p[list(FEATURES)] for p in (parts.train, parts.validation, parts.test)
    )
    X_prod = pd.concat([X_train, X_val])
    minutes: dict[str, np.ndarray] = {}

    order = ["min", *[t for t in targets if t != "min"]]
    for target in order:
        y_train, y_val, y_test = (
            p[target].to_numpy(float) for p in (parts.train, parts.validation, parts.test)
        )
        evaluated, scores = {}, {}
        for algorithm in ALGORITHMS:
            fitted = fit_select(algorithm, target, X_train, y_train, X_val, y_val, config)
            evaluated[algorithm] = fitted
            scores[algorithm] = {
                "params": fitted.params,
                "validation": _slices(parts.validation, y_val, fitted.predict(X_val)),
                "test": _slices(parts.test, y_test, fitted.predict(X_test)),
            }
            log.info(
                "trained",
                extra={
                    "target": target,
                    "algorithm": algorithm,
                    "validation_mae": fitted.validation_mae,
                },
            )
        baseline_test_mae = scores["rolling_baseline"]["test"]["mae"]
        for s in scores.values():
            s["test"]["baseline_mae"] = baseline_test_mae
            s["test"]["mae_reduction_vs_baseline"] = 1 - s["test"]["mae"] / baseline_test_mae
        selected = min(evaluated, key=lambda a: evaluated[a].validation_mae)
        chosen = evaluated[selected]
        if target == "min":
            minutes = {"validation": chosen.predict(X_val), "test": chosen.predict(X_test)}
        conformal = MondrianConformal.fit(y_val - chosen.predict(X_val), minutes["validation"])
        coverage = conformal.coverage(y_test, chosen.predict(X_test), minutes["test"])

        production = refit(chosen, target, X_prod, np.concatenate([y_train, y_val]), config)
        if target == "min":
            minutes["production_test"] = production.predict(X_test)
        production_conformal = MondrianConformal.fit(
            y_test - production.predict(X_test), minutes["production_test"]
        )
        if target in targets:
            result.targets[target] = TargetOutcome(
                target=target,
                evaluated=evaluated,
                scores=scores,
                selected=selected,
                conformal=conformal,
                test_coverage=coverage,
                production=production,
                production_conformal=production_conformal,
            )

    if classify:
        y = {
            name: p["double_double"].to_numpy(int)
            for name, p in (
                ("train", parts.train),
                ("validation", parts.validation),
                ("test", parts.test),
            )
        }
        held_out = fit_classifier(X_train, y["train"], X_val, y["validation"], config)
        production = fit_classifier(
            X_prod,
            np.concatenate([y["train"], y["validation"]]),
            X_test,
            y["test"],
            config,
            algorithm=held_out.algorithm,
        )
        result.double_double = ClassifierOutcome(
            held_out=held_out,
            validation=metrics.classification(y["validation"], held_out.predict_proba(X_val)),
            test=metrics.classification(y["test"], held_out.predict_proba(X_test)),
            production=production,
        )
    result.seconds = time.perf_counter() - started
    return result


def _git_sha() -> tuple[str | None, bool]:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
            ).stdout.strip()
        )
        return sha, dirty
    except (OSError, subprocess.CalledProcessError):
        return None, False


def report(result: TrainingResult, data_version: int, leakage: int, rows: int) -> dict[str, Any]:
    parts = result.splits
    dates = {
        name: [str(d.date()) for d in parts.date_range(name)]
        for name in ("train", "validation", "test")
    }
    return {
        "data_version": data_version,
        "feature_schema_version": feature_schema_version(),
        "features": len(FEATURES),
        "plan": result.plan.describe(),
        "dates": dates,
        "rows": {
            "total": rows,
            "train": len(parts.train),
            "validation": len(parts.validation),
            "test": len(parts.test),
        },
        "leakage_violations": leakage,
        "chronological": parts.chronological,
        "seed": result.config.seed,
        "seconds": round(result.seconds, 1),
        "library_versions": library_versions(),
        "targets": {
            t: {
                "selected": o.selected,
                "algorithms": o.scores,
                "test_interval_coverage": o.test_coverage,
                "conformal_validation": o.conformal.to_dict(),
                "conformal_production": o.production_conformal.to_dict(),
            }
            for t, o in result.targets.items()
        },
        "double_double": None
        if result.double_double is None
        else {
            "algorithm": result.double_double.held_out.algorithm,
            "raw_validation_log_loss": result.double_double.held_out.raw_validation_log_loss,
            "validation": result.double_double.validation,
            "test": result.double_double.test,
        },
    }


def _release_version(session) -> str:
    today = datetime.now(UTC).strftime("%Y.%m.%d")
    count = session.scalar(select(func.count()).where(ModelRelease.version.like(f"{today}-%"))) or 0
    return f"{today}-{count + 1}"


def write_release(
    result: TrainingResult,
    summary: dict[str, Any],
    engine: Engine,
    artifacts_dir: Path,
    data_version: int,
) -> str:
    sha, dirty = _git_sha()
    summary["git_sha"], summary["git_dirty"] = sha, dirty
    parts = result.splits
    with session_scope(engine) as session:
        version = _release_version(session)
        directory = artifacts_dir / version
        summary["release"] = version
        (train_start, train_end), (val_start, val_end), (test_start, test_end) = (
            parts.date_range(n) for n in ("train", "validation", "test")
        )
        release = ModelRelease(
            version=version,
            feature_schema_version=feature_schema_version(),
            train_start=train_start.date(),
            train_end=train_end.date(),
            val_start=val_start.date(),
            val_end=val_end.date(),
            test_start=test_start.date(),
            test_end=test_end.date(),
            data_version=data_version,
            git_sha=sha,
            status=ReleaseStatus.candidate,
        )
        session.add(release)
        session.flush()
        seed = result.config.seed

        def add_version(
            target: str,
            algorithm: str,
            model: Any,
            params: dict,
            fit: str,
            persist: bool,
            conformal: dict | None,
            selected: bool,
            features: tuple[str, ...] = FEATURES,
        ) -> ModelVersion:
            path, digest = NOT_PERSISTED, ""
            if persist:
                relative = f"{version}/{target}__{algorithm}__{fit}.joblib"
                digest = save_artifact(
                    artifacts_dir / relative,
                    model,
                    target=target,
                    algorithm=algorithm,
                    fit=fit,
                    params=params,
                    conformal=conformal,
                    release=version,
                )
                path = relative
            row = ModelVersion(
                release_id=release.id,
                target=ModelTarget(target),
                algorithm=Algorithm(algorithm),
                is_selected=selected,
                hyperparameters={**params, "fit": fit},
                features=list(features),
                interval_calibration=conformal,
                artifact_path=path,
                artifact_sha256=digest,
                random_seed=seed,
            )
            session.add(row)
            session.flush()
            return row

        def add_evaluation(
            row: ModelVersion,
            which: EvaluationSplit,
            season: int,
            s: dict,
            coverage: float | None = None,
        ) -> None:
            session.add(
                ModelEvaluation(
                    model_version_id=row.id,
                    split=which,
                    season_id=season,
                    n_observations=s["n"],
                    mae=s.get("mae"),
                    rmse=s.get("rmse"),
                    r2=s.get("r2"),
                    interval_level=0.80 if coverage is not None else None,
                    interval_coverage=coverage,
                    brier=s.get("brier"),
                    log_loss=s.get("log_loss"),
                    baseline_mae=s.get("baseline_mae"),
                )
            )

        for target, outcome in result.targets.items():
            for algorithm, fitted in outcome.evaluated.items():
                chosen = algorithm == outcome.selected
                row = add_version(
                    target,
                    algorithm,
                    fitted.model,
                    fitted.params,
                    "held_out",
                    chosen,
                    outcome.conformal.to_dict() if chosen else None,
                    False,
                )
                scores = outcome.scores[algorithm]
                add_evaluation(
                    row, EvaluationSplit.validation, result.plan.validation, scores["validation"]
                )
                coverage = outcome.test_coverage["overall"] if chosen else None
                add_evaluation(
                    row, EvaluationSplit.test, result.plan.test, scores["test"], coverage
                )
            add_version(
                target,
                outcome.selected,
                outcome.production.model,
                outcome.production.params,
                "production",
                True,
                outcome.production_conformal.to_dict(),
                True,
            )

        if result.double_double:
            dd = result.double_double
            row = add_version(
                "double_double",
                dd.held_out.algorithm,
                dd.held_out.model,
                {},
                "held_out",
                True,
                None,
                False,
            )
            add_evaluation(row, EvaluationSplit.validation, result.plan.validation, dd.validation)
            add_evaluation(row, EvaluationSplit.test, result.plan.test, dd.test)
            add_version(
                "double_double",
                dd.production.algorithm,
                dd.production.model,
                {},
                "production",
                True,
                None,
                True,
            )

        if result.team:
            team = result.team
            for algorithm, fitted in team.evaluated.items():
                chosen = algorithm == team.selected
                row = add_version(
                    "team_pts", algorithm, fitted.model, fitted.params, "held_out", chosen,
                    team.conformal.to_dict() if chosen else None, False, TEAM_FEATURES,
                )  # fmt: skip
                scores = team.scores[algorithm]
                add_evaluation(row, EvaluationSplit.validation, result.plan.validation,
                               scores["validation"])  # fmt: skip
                cover = team.test_coverage["overall"] if chosen else None
                add_evaluation(row, EvaluationSplit.test, result.plan.test, scores["test"], cover)
            add_version(
                "team_pts", team.selected, team.production.model, team.production.params,
                "production", True, team.production_conformal.to_dict(), True, TEAM_FEATURES,
            )  # fmt: skip
            row = add_version(
                "home_win", "logistic", team.production_win_model, {"input": "predicted_margin"},
                "production", True, None, True, ("predicted_margin",),
            )  # fmt: skip
            add_evaluation(row, EvaluationSplit.test, result.plan.test,
                           {"n": team.win["games"], "brier": team.win["brier"]})  # fmt: skip

        directory.mkdir(parents=True, exist_ok=True)
        (directory / "report.json").write_text(json.dumps(summary, indent=2, default=str))
    return version


def run(
    engine: Engine,
    artifacts_dir: Path,
    config: TrainConfig,
    targets: tuple[str, ...] = TARGETS,
    register: bool = True,
) -> dict[str, Any]:
    dataset = load_dataset(engine)
    if dataset.leakage_violations:
        raise RuntimeError(
            f"{dataset.leakage_violations} rows use data from on or after their game"
        )
    result = train_release(dataset.frame, config, targets=targets, classify=register)
    summary = report(result, dataset.data_version, dataset.leakage_violations, len(dataset.frame))
    if register:
        result.team = train_team(team_frame(load_team_games(engine)), config, result.plan)
        summary["team"] = {
            "selected": result.team.selected,
            "scores": result.team.scores,
            "test_interval_coverage": result.team.test_coverage,
            "win": result.team.win,
        }
    if register:
        write_release(result, summary, engine, artifacts_dir, dataset.data_version)
    return summary
