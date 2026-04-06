from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def to_error_response(error: AppError, request_id: str | None = None):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=error.status_code,
        content={
            "error": {
                "code": error.code,
                "message": error.message,
                "details": error.details,
            },
            "request_id": request_id,
        },
    )


async def _handle_app_error(_request: Any, exc: AppError):
    from infra.core.context import get_request_context

    context = get_request_context()
    return to_error_response(exc, request_id=context.request_id if context else None)


async def _handle_http_exception(_request: Any, exc: Any):
    from infra.core.context import get_request_context

    context = get_request_context()
    error = AppError(
        code="http_error",
        message=str(exc.detail),
        status_code=exc.status_code,
    )
    return to_error_response(error, request_id=context.request_id if context else None)


async def _handle_unexpected_error(_request: Any, exc: Exception):
    from infra.core.context import get_request_context

    context = get_request_context()
    request_id = context.request_id if context else None
    logger.exception("Unhandled application error", exc_info=exc)
    error = AppError(
        code="internal_error",
        message="Internal server error",
        status_code=500,
    )
    return to_error_response(error, request_id=request_id)


def register_exception_handlers(app: Any) -> None:
    from fastapi import HTTPException

    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(HTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unexpected_error)
