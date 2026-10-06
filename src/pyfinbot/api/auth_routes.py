"""
Login endpoint — issues JWT access tokens.

Note: there is no separate username/email field on User. The OAuth2
password form's "username" is the same string as User.id.

Failed logins count against the same throttle as the web sign-in form
(core.login_throttle), by account and by client address.
"""
from __future__ import annotations

import math
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from greentechhub_fastapi.auth import resolve_dependency
from greentechhub_core.security import account_key, client_key, verify_password
from greentechhub_core.types import UnauthorizedError
from fastapi.security import OAuth2PasswordRequestForm

from ..core.login_throttle import LOGIN_THROTTLE
from ..core.security import create_access_token
from ..db.session import get_session
from ..models.user_models import User

router = APIRouter(prefix="/auth", tags=["Auth"])


def _locked_out(retry_after: timedelta) -> HTTPException:
    """429 with Retry-After, worded like LoginViews' lockout message;
    register_api_error_handlers answers it in the {code, message} envelope."""
    seconds = max(1, math.ceil(retry_after.total_seconds()))
    minutes = math.ceil(seconds / 60)
    message = f"Too many failed sign-ins. Try again in {minutes} minute{'' if minutes == 1 else 's'}."
    return HTTPException(429, detail=message, headers={"Retry-After": str(seconds)})


async def _password_ok(request: Request, user_id: str, password: str) -> bool:
    # Its own session, closed before the throttle writes in its sessions
    # (not Depends(get_session), which would stay open around them).
    async with resolve_dependency(request.app, get_session) as session:
        user = await session.get(User, user_id)
        return bool(user and user.password_hash and verify_password(password, user.password_hash))


@router.post("/login")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    keys = [account_key(form_data.username)]
    if request.client:
        keys.append(client_key(request.client.host))
    status = await LOGIN_THROTTLE.check(*keys)
    if not status.allowed and status.retry_after is not None:
        raise _locked_out(status.retry_after)

    if not await _password_ok(request, form_data.username, form_data.password):
        status = await LOGIN_THROTTLE.record_failure(*keys)
        if not status.allowed and status.retry_after is not None:
            raise _locked_out(status.retry_after)
        # 401 envelope + WWW-Authenticate: Bearer (fastapi's register_api_error_handlers).
        raise UnauthorizedError("Incorrect user ID or password")

    # The account only: one good login mustn't wipe a client's count.
    await LOGIN_THROTTLE.record_success(account_key(form_data.username))
    access_token = create_access_token(data={"sub": form_data.username})
    return {"access_token": access_token, "token_type": "bearer"}
