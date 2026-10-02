from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from greentechhub_core.identity import Identity
from greentechhub_fastapi.permissions import get_permission_resolver
from sqlmodel.ext.asyncio.session import AsyncSession

from .security import decode_access_token
from ..db.session import get_session
from ..models.user_models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        raise unauthorized

    user_id = payload.get("sub")
    if not user_id:
        raise unauthorized

    user = await session.get(User, user_id)
    if not user:
        raise unauthorized

    return user


def require_api_permission(permission: str):
    """A Depends() for the bearer-token API: the current User (as
    get_current_user, 401 without a valid token), or 403 unless the app's
    permission resolver (register_permissions) grants them `permission`.
    The API twin of greentechhub_fastapi's cookie-based require_permission."""

    async def dependency(request: Request, user: User = Depends(get_current_user)) -> User:
        identity = Identity(subject=str(user.id), username=str(user.id), email=None, groups=[],
                            claims={})
        if permission not in await get_permission_resolver(request).granted(identity):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
        return user

    return dependency
