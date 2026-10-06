"""The login throttle (greentechhub-core's LoginThrottle over the
gth_login_attempts table): 5 failed sign-ins for an account or a client
within 15 minutes lock it out for 15 minutes.

One instance, shared by the web sign-in form (PyFinBotLoginViews) and the
API's /api/auth/login, so a guesser locked out of one can't carry on at
the other."""

from greentechhub_core.security import LoginThrottle
from greentechhub_core.sqlalchemy import SQLAlchemyAttemptStore

from ..db.session import session_factory
from ..models.settings_models import LOGIN_ATTEMPTS_TABLE

LOGIN_THROTTLE = LoginThrottle(
    SQLAlchemyAttemptStore(LOGIN_ATTEMPTS_TABLE, async_session_factory=session_factory)
)
