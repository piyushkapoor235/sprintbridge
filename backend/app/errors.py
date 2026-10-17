"""One error shape for every failure: {detail, code, field_errors, request_id}.

See docs/api-contract.md "Errors". The frontend branches on `code`, never on `detail` text.
"""

import logging
from typing import NoReturn

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("sprintbridge")

_STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHENTICATED",
    402: "PAYMENT_REQUIRED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_ERROR",
    501: "NOT_IMPLEMENTED",
    503: "SERVICE_UNAVAILABLE",
}


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        detail: str,
        field_errors: dict[str, str] | None = None,
    ):
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail
        self.field_errors = field_errors or {}


def planned(step: str) -> NoReturn:
    """Placeholder for contract endpoints whose implementation is a later step in todo.md."""
    raise ApiError(501, "NOT_IMPLEMENTED", f"Planned for step {step}; see todo.md.")


def _body(request: Request, code: str, detail: str, field_errors: dict[str, str] | None = None) -> dict:
    return {
        "detail": detail,
        "code": code,
        "field_errors": field_errors or {},
        "request_id": getattr(request.state, "request_id", None),
    }


async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(_body(request, exc.code, exc.detail, exc.field_errors), status_code=exc.status_code)


async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    field_errors: dict[str, str] = {}
    for err in exc.errors():
        # Drop the leading "body"/"query"/"path" segment so keys match field names.
        loc = [str(part) for part in err.get("loc", ())[1:]] or ["request"]
        field_errors.setdefault(".".join(loc), err.get("msg", "Invalid value."))
    return JSONResponse(
        _body(request, "VALIDATION_ERROR", "Some fields are invalid.", field_errors), status_code=422
    )


async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = _STATUS_CODES.get(exc.status_code, "ERROR")
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return JSONResponse(_body(request, code, detail), status_code=exc.status_code, headers=exc.headers)


async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error request_id=%s", getattr(request.state, "request_id", None))
    return JSONResponse(_body(request, "INTERNAL_ERROR", "Something went wrong."), status_code=500)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unhandled_error)
