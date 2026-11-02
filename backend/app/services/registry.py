"""Read-only views of the model registry (model_releases, model_versions, model_evaluations)."""

import numpy as np
import pandas as pd
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.deps import Context
from app.api.errors import not_found
from app.models import (
    EvaluationSplit,
    ModelEvaluation,
    ModelRelease,
    ModelVersion,
    PredictionEvaluation,
    ReleaseStatus,
    Season,
)
from app.schemas.resources import (
    AlgorithmMetrics,
    CalibrationPoint,
    CoverageBin,
    LiveAccuracy,
    ModelAnalytics,
    ModelReleaseDetail,
    ModelReleaseSummary,
    ModelSnapshot,
    ResidualBin,
    TargetMetrics,
)
from app.services import prediction_lifecycle

REGISTRY_TTL = 300
LIVE_TTL = 120


def _scored_at(session: Session):
    """When a prediction was last scored. Scoring does not advance data_version, so views of scored
    predictions include this in their cache key and change as soon as new results are scored."""
    return session.scalar(select(func.max(PredictionEvaluation.evaluated_at)))


def _versions(session: Session, release: ModelRelease) -> list[ModelVersion]:
    return list(
        session.scalars(select(ModelVersion).where(ModelVersion.release_id == release.id)).all()
    )


def _summary(release: ModelRelease, versions: list[ModelVersion]) -> ModelReleaseSummary:
    return ModelReleaseSummary(
        version=release.version,
        status=release.status.value,
        created_at=release.created_at,
        activated_at=release.activated_at,
        data_version=release.data_version,
        feature_schema_version=release.feature_schema_version,
        train_start=release.train_start,
        train_end=release.train_end,
        val_start=release.val_start,
        val_end=release.val_end,
        test_start=release.test_start,
        test_end=release.test_end,
        git_sha=release.git_sha,
        selected={v.target.value: v.algorithm.value for v in versions if v.is_selected},
    )


def _evaluations(session: Session, versions: list[ModelVersion]) -> dict:
    ids = [v.id for v in versions]
    rows = session.scalars(select(ModelEvaluation).where(ModelEvaluation.model_version_id.in_(ids)))
    return {(e.model_version_id, e.split): e for e in rows}


def _held_out(versions: list[ModelVersion]) -> list[ModelVersion]:
    return [v for v in versions if v.hyperparameters.get("fit") == "held_out"]


def _metrics(versions: list[ModelVersion], evaluations: dict) -> tuple[list, list]:
    selected = {v.target.value: v.algorithm.value for v in versions if v.is_selected}
    target_metrics, algorithms = [], []
    for v in sorted(_held_out(versions), key=lambda v: (v.target.value, v.algorithm.value)):
        test = evaluations.get((v.id, EvaluationSplit.test))
        validation = evaluations.get((v.id, EvaluationSplit.validation))
        chosen = selected.get(v.target.value) == v.algorithm.value
        if v.target.value != "double_double":
            algorithms.append(AlgorithmMetrics(
                target=v.target.value, algorithm=v.algorithm.value, selected=chosen,
                validation_mae=validation.mae if validation else None,
                test_mae=test.mae if test else None, test_rmse=test.rmse if test else None,
                test_r2=test.r2 if test else None,
            ))  # fmt: skip
        if chosen and test:
            target_metrics.append(TargetMetrics(
                target=v.target.value, algorithm=v.algorithm.value, n=test.n_observations,
                mae=test.mae, rmse=test.rmse, r2=test.r2, baseline_mae=test.baseline_mae,
                interval_coverage=test.interval_coverage, brier=test.brier, log_loss=test.log_loss,
            ))  # fmt: skip
    return target_metrics, algorithms


def _test_season(session: Session, versions: list[ModelVersion], evaluations: dict) -> str | None:
    season_id = next(
        (e.season_id for (_, split), e in evaluations.items() if split == EvaluationSplit.test),
        None,
    )
    return session.scalar(select(Season.label).where(Season.id == season_id)) if season_id else None


def list_releases(ctx: Context) -> list[ModelReleaseSummary]:
    def compute() -> list[ModelReleaseSummary]:
        releases = ctx.session.scalars(
            select(ModelRelease).order_by(ModelRelease.created_at.desc())
        ).all()
        return [_summary(r, _versions(ctx.session, r)) for r in releases]

    return ctx.cached("model_releases", REGISTRY_TTL, None, compute)


def release_detail(ctx: Context, version: str) -> ModelReleaseDetail:
    def compute() -> ModelReleaseDetail:
        release = ctx.session.scalar(select(ModelRelease).where(ModelRelease.version == version))
        if release is None:
            raise not_found("model_release", version)
        versions = _versions(ctx.session, release)
        evaluations = _evaluations(ctx.session, versions)
        target_metrics, algorithms = _metrics(versions, evaluations)
        production = [v for v in versions if v.is_selected and v.interval_calibration]
        return ModelReleaseDetail(
            **_summary(release, versions).model_dump(),
            features=versions[0].features if versions else [],
            test_season=_test_season(ctx.session, versions, evaluations),
            selected_metrics=target_metrics,
            algorithms=algorithms,
            interval_calibration={v.target.value: v.interval_calibration for v in production},
        )

    return ctx.cached("model_release", REGISTRY_TTL, version, compute)


def snapshot(ctx: Context) -> ModelSnapshot | None:
    """The active release, or the newest candidate when none is active, with its test metrics."""
    release = ctx.session.scalar(
        select(ModelRelease).order_by(
            (ModelRelease.status == ReleaseStatus.active).desc(), ModelRelease.created_at.desc()
        )
    )
    if release is None:
        return None
    detail = release_detail(ctx, release.version)
    return ModelSnapshot(
        release=ModelReleaseSummary(
            **detail.model_dump(include=set(ModelReleaseSummary.model_fields))
        ),
        test_season=detail.test_season,
        metrics=detail.selected_metrics,
    )


def live(ctx: Context, version: str) -> LiveAccuracy:
    def compute() -> LiveAccuracy:
        release = ctx.session.scalar(select(ModelRelease).where(ModelRelease.version == version))
        if release is None:
            raise not_found("model_release", version)
        summary = prediction_lifecycle.live_accuracy(ctx.session, release.id)
        return LiveAccuracy(
            version=release.version,
            status=release.status.value,
            activated_at=release.activated_at,
            **summary,
        )

    return ctx.cached("model_live", LIVE_TTL, (version, _scored_at(ctx.session)), compute)


RESIDUAL_WIDTH = {"pts": 2.0, "min": 2.0, "reb": 1.0, "ast": 1.0, "fg3m": 0.5, "stl": 0.5,
                  "blk": 0.5}  # fmt: skip
CALIBRATION_BINS = 10

ANALYTICS_SQL = """
    SELECT v.point, v.lower, v.upper, e.actual, e.within_interval, m.point AS minutes, g.game_date
    FROM predictions p
    JOIN prediction_values v ON v.prediction_id = p.id AND v.stat::text = :stat
    JOIN prediction_evaluations e
      ON e.prediction_id = p.id AND e.stat::text = :stat
    JOIN prediction_values m ON m.prediction_id = p.id AND m.stat = 'min'
    JOIN games g ON g.id = p.game_id
    WHERE p.release_id = :release AND p.kind::text = :kind
      AND NOT EXISTS (SELECT 1 FROM predictions newer WHERE newer.supersedes_prediction_id = p.id)"""


def _analytics_version(versions: list[ModelVersion], kind: str, stat: str) -> ModelVersion | None:
    """Backtests come from the chosen held-out model; pregame forecasts from the production one."""
    for v in versions:
        if v.target.value != stat:
            continue
        fit = (v.hyperparameters or {}).get("fit")
        if kind == "backtest" and fit == "held_out" and v.artifact_sha256:
            return v
        if kind == "pregame" and v.is_selected and fit == "production":
            return v
    return None


def analytics(ctx: Context, version: str, stat: str, kind: str) -> ModelAnalytics:
    def compute() -> ModelAnalytics:
        release = ctx.session.scalar(select(ModelRelease).where(ModelRelease.version == version))
        if release is None:
            raise not_found("model_release", version)
        model = _analytics_version(_versions(ctx.session, release), kind, stat)
        frame = pd.read_sql(
            text(ANALYTICS_SQL),
            ctx.session.connection(),
            params={"stat": stat, "kind": kind, "release": release.id},
        )
        empty = ModelAnalytics(
            version=version, kind=kind, stat=stat,
            algorithm=model.algorithm.value if model else None, n=0, first_game=None,
            last_game=None, mae=None, rmse=None, bias=None, interval_level=0.8, coverage=None,
            calibration=[], residuals=[], coverage_by_bin=[],
        )  # fmt: skip
        if frame.empty:
            return empty
        residual = frame["actual"] - frame["point"]
        order = frame["point"].rank(method="first")
        decile = np.ceil(order / len(frame) * CALIBRATION_BINS).clip(1, CALIBRATION_BINS)
        calibration = [
            CalibrationPoint(
                predicted=float(g["point"].mean()), actual=float(g["actual"].mean()), n=len(g)
            )  # fmt: skip
            for _, g in frame.groupby(decile)
        ]
        width = RESIDUAL_WIDTH.get(stat, 1.0)
        low = np.floor(residual.min() / width) * width
        index = np.floor((residual - low) / width).astype(int)
        counts = index.value_counts().sort_index()
        residuals = [
            ResidualBin(
                lower=float(low + i * width),
                upper=float(low + (i + 1) * width),
                n=int(counts.get(i, 0)),
            )  # fmt: skip
            for i in range(int(index.max()) + 1)
        ]
        edges = list((model.interval_calibration or {}).get("edges", [])) if model else []
        bins = np.digitize(frame["minutes"], edges) if edges else np.zeros(len(frame), int)
        bounds = [None, *edges, None]
        by_bin = [
            CoverageBin(
                minutes_from=bounds[b],
                minutes_to=bounds[b + 1],
                n=int((bins == b).sum()),
                coverage=float(frame.loc[bins == b, "within_interval"].mean())
                if (bins == b).any()
                else None,
            )  # fmt: skip
            for b in range(len(edges) + 1)
        ]
        return empty.model_copy(
            update={
                "n": len(frame),
                "first_game": frame["game_date"].min(),
                "last_game": frame["game_date"].max(),
                "mae": float(residual.abs().mean()),
                "rmse": float(np.sqrt((residual**2).mean())),
                "bias": float(residual.mean()),
                "coverage": float(frame["within_interval"].mean()),
                "calibration": calibration,
                "residuals": residuals,
                "coverage_by_bin": by_bin,
            }
        )

    key = (version, stat, kind, _scored_at(ctx.session))
    return ctx.cached("model_analytics", REGISTRY_TTL, key, compute)
