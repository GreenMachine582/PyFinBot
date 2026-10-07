"""
Login endpoint — issues JWT access tokens.

Note: there is no separate username/email field on User. The OAuth2
password form's "username" is the same string as User.id.

Failed logins count against the same throttle as the web sign-in form
(core.login_throttle, through greentechhub-fastapi's throttled_login): a
locked-out attempt is answered 429 with Retry-After, in the API's error
envelope (code "too_many_requests").
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from greentechhub_core.types import UnauthorizedError
from greentechhub_fastapi.auth import client_address, resolve_dependency, throttled_login

from ..core.login_throttle import LOGIN_THROTTLE
from ..core.security import create_access_token
from ..core.users import check_password
from ..db.session import get_session

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    async def check() -> str | None:
        # Its own session, closed before the throttle writes in its own
        # sessions (a Depends(get_session) one would stay open around them).
        async with resolve_dependency(request.app, get_session) as session:
            user = await check_password(session, form_data.username, form_data.password)
            return user.id if user else None

    user_id = await throttled_login(LOGIN_THROTTLE, form_data.username, check,
                                    address=client_address(request))
    if user_id is None:
        # 401 envelope + WWW-Authenticate: Bearer (fastapi's register_api_error_handlers).
        raise UnauthorizedError("Incorrect user ID or password")

    access_token = create_access_token(data={"sub": user_id})
    return {"access_token": access_token, "token_type": "bearer"}
