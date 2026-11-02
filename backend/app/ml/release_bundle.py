import io
import json
import tarfile
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.ingestion.jobs import ensure_season
from app.ml.artifacts import ArtifactMismatch, load_artifact
from app.models import ModelEvaluation, ModelRelease, ModelVersion, Season

BUNDLE_FORMAT = 1
NOT_PERSISTED = ""


def _to_json(obj: Any) -> dict[str, Any]:
    def plain(value: Any) -> Any:
        if isinstance(value, uuid.UUID | Decimal):
            return str(value)
        if isinstance(value, datetime | date):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        return value

    return {c.key: plain(getattr(obj, c.key)) for c in inspect(obj).mapper.column_attrs}


def _from_json(model: type, row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for attr in inspect(model).column_attrs:
        if attr.key not in row:
            continue
        value = row[attr.key]
        kind = attr.columns[0].type.python_type
        if value is not None and not isinstance(value, kind):
            if kind is datetime:
                value = datetime.fromisoformat(value)
            elif kind is date:
                value = date.fromisoformat(value)
            elif kind in (uuid.UUID, Decimal) or issubclass(kind, Enum):
                value = kind(value)
        out[attr.key] = value
    return out


def _release(session: Session, version: str) -> ModelRelease:
    release = session.scalar(select(ModelRelease).where(ModelRelease.version == version))
    if release is None:
        raise LookupError(f"No release {version}")
    return release


def _versions(session: Session, release: ModelRelease) -> list[ModelVersion]:
    return list(session.scalars(select(ModelVersion).where(ModelVersion.release_id == release.id)))


def verify_release(session: Session, artifacts_dir: Path, version: str) -> list[str]:
    problems = []
    for v in _versions(session, _release(session, version)):
        if v.artifact_sha256 == NOT_PERSISTED:
            continue
        try:
            load_artifact(artifacts_dir / v.artifact_path, v.artifact_sha256)
        except FileNotFoundError:
            problems.append(f"{v.artifact_path}: missing")
        except ArtifactMismatch as error:
            problems.append(str(error))
    return problems


def export_release(session: Session, artifacts_dir: Path, version: str, out: Path) -> int:
    problems = verify_release(session, artifacts_dir, version)
    if problems:
        raise ArtifactMismatch("; ".join(problems))
    release = _release(session, version)
    versions = _versions(session, release)
    evaluations = session.scalars(
        select(ModelEvaluation).where(
            ModelEvaluation.model_version_id.in_([v.id for v in versions])
        )
    ).all()
    registry = {
        "format": BUNDLE_FORMAT,
        "release": _to_json(release),
        "versions": [_to_json(v) for v in versions],
        "evaluations": [_to_json(e) for e in evaluations],
    }
    persisted = [v for v in versions if v.artifact_sha256 != NOT_PERSISTED]
    out.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out, "w:gz") as tar:
        data = json.dumps(registry, indent=2, sort_keys=True).encode()
        info = tarfile.TarInfo("registry.json")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
        for v in persisted:
            tar.add(artifacts_dir / v.artifact_path, arcname=f"artifacts/{v.artifact_path}")
    return len(persisted)


def _safe(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ArtifactMismatch(f"unsafe path in bundle: {name}")
    return path


def import_release(session: Session, artifacts_dir: Path, bundle: Path) -> str:
    with tarfile.open(bundle, "r:gz") as tar:
        files = {m.name: m for m in tar.getmembers() if m.isfile()}
        registry = json.loads(tar.extractfile(files["registry.json"]).read())  # type: ignore[union-attr]
        if registry.get("format") != BUNDLE_FORMAT:
            raise ArtifactMismatch(f"unsupported bundle format {registry.get('format')}")
        version = registry["release"]["version"]
        if session.scalar(select(ModelRelease.id).where(ModelRelease.version == version)):
            raise ArtifactMismatch(f"release {version} already exists here")
        for row in registry["versions"]:
            if row["artifact_sha256"] == NOT_PERSISTED:
                continue
            member = files.get(f"artifacts/{_safe(row['artifact_path'])}")
            if member is None:
                raise ArtifactMismatch(f"{row['artifact_path']}: missing from the bundle")
            target = artifacts_dir / _safe(row["artifact_path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(tar.extractfile(member).read())  # type: ignore[union-attr]
            try:
                load_artifact(target, row["artifact_sha256"])
            except ArtifactMismatch:
                target.unlink()
                raise

    release_row = {**registry["release"], "status": "candidate", "activated_at": None}
    session.add(ModelRelease(**_from_json(ModelRelease, release_row)))
    session.flush()
    for row in registry["versions"]:
        session.add(ModelVersion(**_from_json(ModelVersion, row)))
    session.flush()
    for row in registry["evaluations"]:
        if row.get("season_id") and session.get(Season, row["season_id"]) is None:
            ensure_season(session, row["season_id"])
        values = _from_json(ModelEvaluation, row)
        values.pop("id", None)
        session.add(ModelEvaluation(**values))
    session.flush()
    return version
