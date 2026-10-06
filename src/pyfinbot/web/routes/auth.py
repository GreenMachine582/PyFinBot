from datetime import datetime, timezone

from fastapi import APIRouter
from greentechhub_core.identity import DevelopmentIdentityProvider, Identity
from greentechhub_core.security import hash_password, verify_password
from greentechhub_fastapi.auth import LoginViews, resolve_dependency

from ...core.login_throttle import LOGIN_THROTTLE
from ...core.settings import settings
from ...db.session import get_session
from ...models.user_models import User
from ..templating import templates


class PyFinBotLoginViews(LoginViews):
    """Local-auth /login and /logout. The page is greentechhub-ui's
    login_page.html (LoginViews' default since greentechhub-fastapi v0.11),
    so PyFinBot only checks the password. Repeated failures are locked out
    by core.login_throttle (429 + Retry-After, before authenticate runs)."""

    async def authenticate(self, user_id: str, password: str) -> Identity | None:
        # Deferred import: pyfinbot.py imports this module at load time, so a
        # top-level `from ...pyfinbot import app` here would be circular.
        from ...pyfinbot import app

        async with resolve_dependency(app, get_session) as session:
            user = await session.get(User, user_id)
            if not user or not user.password_hash or not verify_password(password, user.password_hash):
                return None
            return Identity(subject=user.id, username=user.id, email=None, groups=[], claims={})


async def change_password(user: Identity, current: str, new: str) -> bool:
    """SettingsViews' change_password hook (/settings › Password): False when
    `current` isn't the user's password, else store the new one's hash.
    greentechhub-fastapi has already checked the new password's length,
    that it differs and that it's confirmed. Sessions already issued stay
    valid; they're stateless JWTs."""
    from ...pyfinbot import app  # deferred for the same reason as authenticate's

    async with resolve_dependency(app, get_session) as session:
        row = await session.get(User, user.subject)
        if not row or not row.password_hash or not verify_password(current, row.password_hash):
            return False
        row.password_hash = hash_password(new)
        row.write_datetime = datetime.now(timezone.utc)
        session.add(row)
        await session.commit()
    return True


def build_router() -> APIRouter | None:
    """Local-auth login/logout routes — only meaningful when
    AUTH_ADAPTER=local. Under forward_auth, Authentik handles login
    externally via the outpost; there's no password form for this app to
    serve. Returns None so pyfinbot.py can skip mounting it, keeping this
    driven by the same AUTH_ADAPTER setting register_auth itself reads,
    rather than this module assuming "local" the way it did before.

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
    ).router()
