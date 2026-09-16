"""One error shape for the whole API.

Clients always receive code, message and optional field details. Internal
exception messages, stack traces and database errors are logged, never returned.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class FieldError(BaseModel):
    field: str
    message: str


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: list[FieldError] | None = None


class ApiError(Exception):
    """Raised by services and routes to produce a predictable error response."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class NotFoundError(ApiError):
    def __init__(self, message: str) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "not_found", message)


class ConflictError(ApiError):
    def __init__(self, message: str) -> None:
        super().__init__(status.HTTP_409_CONFLICT, "conflict", message)


class UnprocessableError(ApiError):
    def __init__(self, message: str) -> None:
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, "validation_failed", message)


def _json(status_code: int, payload: ErrorResponse) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=payload.model_dump(exclude_none=True))


def _field_path(loc: Any) -> str:
    parts = [str(part) for part in loc if part not in ("body", "query", "path")]
    return ".".join(parts) or "request"


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _json(exc.status_code, ErrorResponse(code=exc.code, message=exc.message))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        codes = {
            status.HTTP_404_NOT_FOUND: "not_found",
            status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: "payload_too_large",
        }
        code = codes.get(exc.status_code, f"http_{exc.status_code}")
        message = (
            exc.detail if isinstance(exc.detail, str) else "The request could not be completed."
        )
        return _json(exc.status_code, ErrorResponse(code=code, message=message))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            FieldError(
                field=_field_path(error.get("loc", ())),
                message=str(error.get("msg", "Invalid value.")),
            )
            for error in exc.errors()
        ]
        return _json(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            ErrorResponse(
                code="validation_failed",
                message="The request body or parameters are invalid.",
                details=details,
            ),
        )

    @app.exception_handler(IntegrityError)
    async def _integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
        logger.warning("database integrity error", exc_info=exc)
        return _json(
            status.HTTP_409_CONFLICT,
            ErrorResponse(code="conflict", message="The request conflicts with existing data."),
        )

    @app.exception_handler(SQLAlchemyError)
    async def _database_error(_: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.error("database error", exc_info=exc)
        return _json(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            ErrorResponse(
                code="database_unavailable",
                message="The database is unavailable. Please try again.",
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error", exc_info=exc)
        return _json(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            ErrorResponse(
                code="internal_error", message="Something went wrong. The incident has been logged."
            ),
        )
