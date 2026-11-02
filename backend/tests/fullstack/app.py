import os
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI

from app.logging import configure_logging
from app.main import create_app
from app.services.cache import Memo


def build() -> FastAPI:
    configure_logging()
    app = create_app()
    state = app.state.api
    clock = Path(os.environ["NBA_FULLSTACK_CLOCK"])
    state.clock = lambda: datetime.fromisoformat(clock.read_text().strip())
    state.photos = SimpleNamespace(path=lambda player_id, size="small": None)
    state.version = Memo(0.0)
    state.freshness = Memo(0.0)
    return app
