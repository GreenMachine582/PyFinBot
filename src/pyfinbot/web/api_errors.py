"""Error responses: the {code, message, details} JSON envelope for /api,
FastAPI's defaults for everything else (so the pages' login redirects,
HX-Redirect and HTML errors are unchanged).

greentechhub-fastapi's register_exception_handlers covers core's
ApplicationError hierarchy. This adds, after it:
  - StatusError (core/errors.py): the envelope at its own status (400/502/503);
  - UnauthorizedError: the envelope plus WWW-Authenticate: Bearer (OAuth2);
  - HTTPException raised by the framework on /api (OAuth2PasswordBearer's
    401, unknown routes, 405) and request validation errors: the envelope.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from greentechhub_core.types import UnauthorizedError
from greentechhub_fastapi.exceptions.render import render_error_body
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..core.errors import StatusError

API_PREFIX = "/api"

STATUS_CODES = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found",
                405: "method_not_allowed", 409: "conflict", 422: "validation_error"}


def _is_api(request: Request) -> bool:
    path = request.url.path
    return path == API_PREFIX or path.startswith(API_PREFIX + "/")


def envelope(status_code: int, code: str, message: str, details: Any = None,
             headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, headers=headers,
                        content={"code": code, "message": message, "details": details})


def register_api_error_handlers(app: FastAPI) -> None:
    """Install the handlers above. Call after register_exception_handlers."""

    @app.exception_handler(StatusError)
    async def _status_error(request: Request, exc: StatusError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=render_error_body(exc))

    @app.exception_handler(UnauthorizedError)
    async def _unauthorized(request: Request, exc: UnauthorizedError) -> JSONResponse:
        return JSONResponse(status_code=401, content=render_error_body(exc),
                            headers={"WWW-Authenticate": "Bearer"})

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(request: Request, exc: StarletteHTTPException) -> Response:
        if not _is_api(request):
            return await http_exception_handler(request, exc)
        code = STATUS_CODES.get(exc.status_code, f"http_{exc.status_code}")
        return envelope(exc.status_code, code, str(exc.detail), headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> Response:
        if not _is_api(request):
            return await request_validation_exception_handler(request, exc)
        return envelope(422, "validation_error", "Invalid request", jsonable_encoder(exc.errors()))
