"""Read-only views of the model registry (model_releases, model_versions, model_evaluations)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Context
from app.api.errors import not_found
from app.models import (
    EvaluationSplit,
    ModelEvaluation,
    ModelRelease,
    ModelVersion,
    ReleaseStatus,
    Season,
)
from app.schemas.resources import (
    AlgorithmMetrics,
    LiveAccuracy,
    ModelReleaseDetail,
    ModelReleaseSummary,
    ModelSnapshot,
    TargetMetrics,
)
from app.services import prediction_lifecycle

REGISTRY_TTL = 300
# Scoring does not advance data_version, so live accuracy relies on a short TTL instead.
LIVE_TTL = 120


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

    return ctx.cached("model_live", LIVE_TTL, version, compute)
