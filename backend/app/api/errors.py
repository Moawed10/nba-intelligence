"""Error envelope (docs/api-contracts.md#error-envelope)."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)


class ErrorDetail(BaseModel):
    field: str | None = None
    issue: str


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str | None
    details: list[ErrorDetail] = []


class ErrorResponse(BaseModel):
    error: ErrorBody


class ApiError(Exception):
    def __init__(
        self, status: int, code: str, message: str, details: list[ErrorDetail] | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or []


def not_found(resource: str, identifier: Any) -> ApiError:
    return ApiError(404, f"{resource}_not_found", f"No {resource} with id {identifier}.")


def invalid_parameter(field: str, message: str, issue: str = "invalid") -> ApiError:
    return ApiError(400, "invalid_parameter", message, [ErrorDetail(field=field, issue=issue)])


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: {"model": ErrorResponse} for status in (400, 404, 409, 422, 503)
}

HTTP_CODES = {404: "not_found", 405: "method_not_allowed", 413: "payload_too_large"}


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def error_response(
    request: Request, status: int, code: str, message: str,
    details: list[ErrorDetail] | None = None, headers: dict[str, str] | None = None,
) -> JSONResponse:  # fmt: skip
    request_id = _request_id(request)
    body = ErrorResponse(
        error=ErrorBody(code=code, message=message, request_id=request_id, details=details or [])
    )
    response = JSONResponse(body.model_dump(), status_code=status, headers=headers)
    if request_id:
        response.headers["X-Request-ID"] = request_id
    return response


def _field(loc: tuple[Any, ...]) -> str:
    parts = [str(p) for p in loc if p not in ("query", "path", "body")]
    return ".".join(parts) or "request"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError) -> JSONResponse:
        return error_response(request, exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [ErrorDetail(field=_field(e["loc"]), issue=e["type"]) for e in exc.errors()]
        return error_response(
            request, 422, "validation_error", "The request parameters are invalid.", details
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = HTTP_CODES.get(exc.status_code, "http_error")
        message = "Resource not found." if exc.status_code == 404 else str(exc.detail)
        return error_response(request, exc.status_code, code, message, headers=exc.headers)

    @app.exception_handler(OperationalError)
    async def database_error(request: Request, exc: OperationalError) -> JSONResponse:
        log.error("database unavailable", extra={"request_id": _request_id(request)})
        return error_response(
            request, 503, "database_unavailable", "The database is temporarily unavailable."
        )

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error", extra={"request_id": _request_id(request)})
        return error_response(request, 500, "internal_error", "An unexpected error occurred.")
