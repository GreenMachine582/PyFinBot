from fastapi import APIRouter
from greentechhub_core.identity import DevelopmentIdentityProvider
from greentechhub_fastapi.users import AccountLoginViews, account_password_change

from ...core.login_throttle import LOGIN_THROTTLE
from ...core.settings import settings
from ...core.users import USER_STORE
from ..templating import templates
from .account_email import RESET_VIEWS, VERIFY_VIEWS


class PyFinBotLoginViews(AccountLoginViews):
    """Local-auth /login and /logout over the user accounts (core/users.py):
    greentechhub-fastapi checks the password against USER_STORE, so
    PyFinBot writes no credential code. The page is greentechhub-ui's
    login_page.html, with "Forgot password?" (web/routes/account_email.py).
    Repeated failures are locked out by core.login_throttle (429 +
    Retry-After, before the password is checked).

    The form carries a CSRF token (fastapi's double-submit `gth_csrf`
    cookie, rendered by ui's login page): a POST without it is refused 403
    before anything else. So does POST /logout (the navbar's logout form
    sends it). Like the session cookie it needs HTTPS, or localhost, which
    browsers treat as secure."""

    csrf = True
    logout_csrf = True
    forgot_password_url = RESET_VIEWS.forgot_url
    verify_resend_url = VERIFY_VIEWS.resend_url


#: SettingsViews' change_password hook (/settings › Password): False when
#: `current` isn't the account's password (or it has none: an Authentik-only
#: account), else store the new one's hash. greentechhub-fastapi has already
#: checked the new password's length, that it differs and that it's
#: confirmed.
change_password = account_password_change(USER_STORE)


def build_router() -> APIRouter | None:
    """Local-auth login/logout routes — only meaningful when
    AUTH_ADAPTER=local. Under forward_auth, Authentik handles login
    externally via the outpost; there's no password form for this app to
    serve. Returns None so pyfinbot.py can skip mounting it, keeping this
    driven by the same AUTH_ADAPTER setting register_auth itself reads.

    Safe to check settings.auth_adapter (core's GTHBaseSettings field, env
    AUTH_ADAPTER) without re-validating it here:
    register_auth(app, settings) is called earlier in pyfinbot.py and
    raises ValueError on anything other than "local"/"forward_auth", so by
    the time this runs it's already known-valid.
    """
    if settings.auth_adapter != "local":
        return None
    return PyFinBotLoginViews(
        templates=templates,
        identity_provider=DevelopmentIdentityProvider(secret_key=settings.secret_key),
        throttle=LOGIN_THROTTLE,
        users=USER_STORE,
    ).router()
