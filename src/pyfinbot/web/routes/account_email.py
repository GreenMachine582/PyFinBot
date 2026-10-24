"""The emailed-link pages for local accounts (greentechhub-fastapi's
store-backed views over core/users.py): "Forgot password?" at
/forgot-password, and the email confirmation link a changed address gets
from /settings › Profile, at /verify-email (resend at /verify-email/resend).

Both email through register_email (pyfinbot.py), so they need the mail
server set at Settings › App › Outgoing email and BASE_URL for absolute
links; until then the forms still answer the same and log the failure.
Local sign-in only: behind Authentik, it owns passwords and addresses.
"""

from greentechhub_core.security import OneTimeTokens
from greentechhub_core.sqlalchemy import SQLAlchemyTokenStore
from greentechhub_fastapi.users import AccountPasswordResetViews, AccountVerificationViews

from ...core.login_throttle import LOGIN_THROTTLE
from ...core.users import USER_STORE
from ...db.session import session_factory
from ...models.settings_models import ONE_TIME_TOKENS_TABLE
from ..templating import templates

TOKENS = OneTimeTokens(SQLAlchemyTokenStore(ONE_TIME_TOKENS_TABLE,
                                            async_session_factory=session_factory))


class _ResetViews(AccountPasswordResetViews):
    csrf = True


class _VerifyViews(AccountVerificationViews):
    csrf = True


RESET_VIEWS = _ResetViews(templates=templates, tokens=TOKENS, throttle=LOGIN_THROTTLE,
                          users=USER_STORE)
VERIFY_VIEWS = _VerifyViews(templates=templates, tokens=TOKENS, throttle=LOGIN_THROTTLE,
                            users=USER_STORE)
