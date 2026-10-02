"""PyFinBot's addition to greentechhub-core's ApplicationError hierarchy.

The API raises core's errors (NotFoundError, ForbiddenError, ConflictError,
UnauthorizedError, ValidationError), which greentechhub-fastapi's
register_exception_handlers answers as the {code, message, details} JSON
envelope. Its status map has no 400 / 502 / 503, so StatusError carries its
own status for those (web/api_errors.py answers it).
"""

from typing import Any

from greentechhub_core.types import ApplicationError


class StatusError(ApplicationError):
    """An ApplicationError with an explicit HTTP status, e.g. a 400
    "stock_exists" or a 503 "email_sync_failed"."""

    code = "bad_request"

    def __init__(self, message: str, *, status_code: int = 400, code: str | None = None,
                 details: Any = None) -> None:
        super().__init__(message, code=code, details=details)
        self.status_code = status_code
