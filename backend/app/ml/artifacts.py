"""Model artifacts: joblib payloads with their feature schema, verified by SHA-256 on load."""

import hashlib
from importlib.metadata import version
from pathlib import Path
from typing import Any

import joblib

from app.ml.features import FEATURES, feature_schema_version

ARTIFACT_FORMAT = 1
LIBRARIES = ("scikit-learn", "xgboost", "numpy", "pandas", "joblib")


class ArtifactMismatch(RuntimeError):
    pass


def library_versions() -> dict[str, str]:
    return {name: version(name) for name in LIBRARIES}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_artifact(path: Path, model: Any, **metadata: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": ARTIFACT_FORMAT,
        "feature_schema_version": feature_schema_version(),
        "features": list(FEATURES),
        "library_versions": library_versions(),
        "model": model,
        **metadata,
    }
    joblib.dump(payload, path, compress=3)
    return sha256(path)


def load_artifact(path: Path, expected_sha256: str) -> dict[str, Any]:
    """Refuses artifacts whose bytes or feature schema differ from the registry or running code."""
    actual = sha256(path)
    if actual != expected_sha256:
        raise ArtifactMismatch(f"{path.name}: SHA-256 {actual} does not match the registry")
    payload = joblib.load(path)
    if payload.get("feature_schema_version") != feature_schema_version():
        raise ArtifactMismatch(f"{path.name}: feature schema differs from the running code")
    return payload
