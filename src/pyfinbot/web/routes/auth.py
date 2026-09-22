from fastapi import APIRouter
from greentechhub_core.identity import DevelopmentIdentityProvider, Identity
from greentechhub_fastapi.auth import LoginViews, resolve_dependency

from ...core.security import verify_password
from ...core.settings import settings
from ...db.session import get_session
from ...models.user_models import User
from ..templating import templates


class PyFinBotLoginViews(LoginViews):
    async def authenticate(self, user_id: str, password: str) -> Identity | None:
        # Deferred import: pyfinbot.py imports this module at load time, so a
        # top-level `from ...pyfinbot import app` here would be circular.
        from ...pyfinbot import app

        async with resolve_dependency(app, get_session) as session:
            user = await session.get(User, user_id)
            if not user or not user.password_hash or not verify_password(password, user.password_hash):
                return None
            return Identity(subject=user.id, username=user.id, email=None, groups=[], claims={})


def build_router() -> APIRouter | None:
    """Local-auth login/logout routes — only meaningful when
    AUTH_ADAPTER=local. Under forward_auth, Authentik handles login
    externally via the outpost; there's no password form for this app to
    serve. Returns None so pyfinbot.py can skip mounting it, keeping this
    driven by the same AUTH_ADAPTER setting register_auth itself reads,
    rather than this module assuming "local" the way it did before.

    Safe to check settings.AUTH_ADAPTER without re-validating it here:
    register_auth(app, settings) is called earlier in pyfinbot.py and
    raises ValueError on anything other than "local"/"forward_auth", so by
    the time this runs it's already known-valid.
    """
    if settings.AUTH_ADAPTER != "local":
        return None
    return PyFinBotLoginViews(
        templates=templates,
        identity_provider=DevelopmentIdentityProvider(secret_key=settings.secret_key),
    ).router()
