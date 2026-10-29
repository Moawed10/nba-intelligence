import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ml.artifacts import load_artifact
from app.ml.dataset import training_frame
from app.ml.features import TARGETS, feature_schema_version
from app.ml.models import FAST_CONFIG
from app.ml.train import NOT_PERSISTED, report, train_release, write_release
from app.models import ModelEvaluation, ModelRelease, ModelVersion, ReleaseStatus, Season
from tests.ml_fixtures import PLAN, SEASONS, league

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def trained():
    frame = training_frame(*league())
    return train_release(frame, FAST_CONFIG, PLAN), len(frame)


def test_release_is_registered_with_artifacts_and_evaluations(engine, trained, tmp_path):
    result, rows = trained
    with Session(engine) as s, s.begin():
        s.add_all([Season(id=y, label=f"{y}-{(y + 1) % 100:02d}") for y in SEASONS])
    summary = report(result, data_version=42, leakage=0, rows=rows)
    version = write_release(result, summary, engine, tmp_path, data_version=42)

    with Session(engine) as s:
        release = s.scalar(select(ModelRelease).where(ModelRelease.version == version))
        assert release.status == ReleaseStatus.candidate
        assert release.data_version == 42
        assert release.feature_schema_version == feature_schema_version()
        assert release.train_end < release.val_start < release.val_end < release.test_start

        versions = s.scalars(
            select(ModelVersion).where(ModelVersion.release_id == release.id)
        ).all()
        selected = [v for v in versions if v.is_selected]
        assert sorted(v.target.value for v in selected) == sorted([*TARGETS, "double_double"])
        assert len(versions) == len(TARGETS) * 5 + 2
        for v in versions:
            if v.artifact_path == NOT_PERSISTED:
                assert not v.is_selected
                continue
            payload = load_artifact(tmp_path / v.artifact_path, v.artifact_sha256)
            assert payload["target"] == v.target.value
            assert payload["release"] == version
        for v in selected:
            if v.target.value != "double_double":
                assert v.interval_calibration["method"] == "mondrian_split_conformal"

        evaluations = s.scalar(select(func.count()).select_from(ModelEvaluation))
        assert evaluations == len(TARGETS) * 4 * 2 + 2
        coverage = s.scalars(
            select(ModelEvaluation.interval_coverage).where(
                ModelEvaluation.interval_coverage.is_not(None)
            )
        ).all()
        assert len(coverage) == len(TARGETS)
    assert (tmp_path / version / "report.json").exists()
