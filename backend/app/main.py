import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine

from app.api import v1
from app.api.deps import ApiState
from app.api.errors import register_error_handlers
from app.config import get_settings
from app.db import api_engine
from app.logging import configure_logging
from app.services.cache import VersionedCache

log = logging.getLogger("app.access")
REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def create_app(engine: Engine | None = None) -> FastAPI:
    settings = get_settings()
    docs = settings.api_docs_enabled
    app = FastAPI(
        title="NBA Intelligence API",
        version="0.1.0",
        description="Read-only NBA statistics from stored, verified data. No public write "
        "or administrative operations.",
        openapi_url="/api/v1/openapi.json" if docs else None,
        docs_url="/api/v1/docs" if docs else None,
        redoc_url=None,
    )
    app.state.api = ApiState(
        engine=engine or api_engine(), cache=VersionedCache(enabled=settings.api_cache_enabled)
    )
    register_error_handlers(app)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-Request-ID"],
            expose_headers=["X-Request-ID"],
        )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if REQUEST_ID.match(incoming) else str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        log.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
        return response

    app.include_router(v1.router)
    return app


def build() -> FastAPI:
    configure_logging()
    return create_app()
