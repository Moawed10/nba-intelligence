import io
import tarfile

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.cli import main
from app.ml.artifacts import ArtifactMismatch
from app.ml.inference import activate
from app.ml.release_bundle import export_release, import_release, verify_release
from app.models import ModelEvaluation, ModelRelease, ModelVersion, ReleaseStatus
from tests.api.conftest import NOW
from tests.api.test_predictions import _release, league  # noqa: F401

pytestmark = pytest.mark.integration

VERSION = "2099.11.10-1"


@pytest.fixture
def released(league, tmp_path):  # noqa: F811
    artifacts = tmp_path / "artifacts"
    _release(league, artifacts, VERSION, ReleaseStatus.candidate)
    return artifacts


def _forget(engine, version: str) -> None:
    with Session(engine) as s, s.begin():
        release = s.scalar(select(ModelRelease).where(ModelRelease.version == version))
        ids = s.scalars(select(ModelVersion.id).where(ModelVersion.release_id == release.id)).all()
        s.execute(delete(ModelEvaluation).where(ModelEvaluation.model_version_id.in_(ids)))
        s.execute(delete(ModelVersion).where(ModelVersion.release_id == release.id))
        s.delete(release)


def test_verify_reports_missing_and_altered_artifacts(league, released):  # noqa: F811
    with Session(league) as s:
        assert verify_release(s, released, VERSION) == []
        files = sorted(released.rglob("*.joblib"))
        files[0].unlink()
        files[1].write_bytes(files[1].read_bytes() + b"x")
        problems = verify_release(s, released, VERSION)
    assert len(problems) == 2
    assert any("missing" in p for p in problems) and any("SHA-256" in p for p in problems)


def test_a_release_moves_to_another_machine_and_activates(league, released, tmp_path):  # noqa: F811
    bundle = tmp_path / "release.tar.gz"
    with Session(league) as s:
        count = export_release(s, released, VERSION, bundle)
        hashes = sorted(s.scalars(select(ModelVersion.artifact_sha256)).all())
    assert count == len(hashes) > 0
    _forget(league, VERSION)
    elsewhere = tmp_path / "other-machine"
    with Session(league) as s, s.begin():
        assert import_release(s, elsewhere, bundle) == VERSION
    with Session(league) as s, s.begin():
        imported = s.scalar(select(ModelRelease).where(ModelRelease.version == VERSION))
        assert imported.status == ReleaseStatus.candidate
        assert verify_release(s, elsewhere, VERSION) == []
        assert sorted(s.scalars(select(ModelVersion.artifact_sha256)).all()) == hashes
        activate(s, VERSION, elsewhere, NOW)
        assert imported.status == ReleaseStatus.active


def test_import_refuses_a_tampered_bundle_and_keeps_the_registry_unchanged(
    league,  # noqa: F811
    released,
    tmp_path,
):
    bundle = tmp_path / "release.tar.gz"
    with Session(league) as s:
        export_release(s, released, VERSION, bundle)
    _forget(league, VERSION)
    tampered = tmp_path / "tampered.tar.gz"
    with tarfile.open(bundle, "r:gz") as src, tarfile.open(tampered, "w:gz") as dst:
        changed = False
        for member in src.getmembers():
            data = src.extractfile(member).read()
            if member.name.endswith(".joblib") and not changed:
                data, changed = data + b"tampered", True
                member.size = len(data)
            dst.addfile(member, io.BytesIO(data))
    with Session(league) as s, pytest.raises(ArtifactMismatch):
        import_release(s, tmp_path / "target", tampered)
    with Session(league) as s:
        assert s.scalar(select(ModelRelease).where(ModelRelease.version == VERSION)) is None


def test_cli_verifies_and_rejects_an_unknown_release(league, released, monkeypatch, capsys):  # noqa: F811
    from app.config import get_settings

    monkeypatch.setattr("app.cli.get_engine", lambda: league)
    monkeypatch.setattr(get_settings(), "artifacts_dir", released)
    assert main(["artifacts", "verify", VERSION]) == 0
    assert "all artifacts verified" in capsys.readouterr().out
    assert main(["artifacts", "verify", "2000.01.01-1"]) == 1
