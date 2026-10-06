"""The login throttle (greentechhub-core's LoginThrottle over the
gth_login_attempts table): 5 failed sign-ins for an account or a client
within 15 minutes lock it out for 15 minutes.

The web sign-in form (PyFinBotLoginViews) uses it; /api/auth/login is to
share it through greentechhub-fastapi's throttled_login (todo.md)."""

from greentechhub_core.security import LoginThrottle
from greentechhub_core.sqlalchemy import SQLAlchemyAttemptStore

from ..db.session import session_factory
from ..models.settings_models import LOGIN_ATTEMPTS_TABLE

LOGIN_THROTTLE = LoginThrottle(
    SQLAlchemyAttemptStore(LOGIN_ATTEMPTS_TABLE, async_session_factory=session_factory)
)
