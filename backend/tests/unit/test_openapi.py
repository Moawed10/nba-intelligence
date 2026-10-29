from pathlib import Path

from app.cli import openapi_json

SCHEMA = Path(__file__).resolve().parents[2] / "openapi.json"


def test_committed_schema_matches_the_app():
    """Regenerate: python -m app.cli openapi > openapi.json, then npm run api:types."""
    assert SCHEMA.read_text() == openapi_json()
