"""
Login endpoint — issues API tokens (greentechhub-fastapi's issue_token).

The OAuth2 password form's "username" is the account's username; the
token's subject is the account id (core/users.py), the same one every route
keys on.

Failed logins count against the same throttle as the web sign-in form
(core.login_throttle, through greentechhub-fastapi's throttled_login): a
locked-out attempt is answered 429 with Retry-After, in the API's error
envelope (code "too_many_requests").
"""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from greentechhub_core.identity import Identity
from greentechhub_core.types import UnauthorizedError
from greentechhub_core.users import account_identity, authenticate
from greentechhub_fastapi.auth import client_address, issue_token, throttled_login
from greentechhub_fastapi.dependencies import get_current_identity

from ..core.login_throttle import LOGIN_THROTTLE
from ..core.users import USER_STORE
from ..schemas.user_schemas import UserBase, user_out

router = APIRouter(prefix="/auth", tags=["Auth"])

# How long an API token from /api/auth/login is valid (todo › Known
# limitations: stateless, no revocation — but a deactivated account's
# tokens stop working at once, since every request reads the account).
API_TOKEN_LIFETIME = timedelta(hours=24)


@router.post("/login")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    async def check() -> Identity | None:
        account = await authenticate(USER_STORE, form_data.username, form_data.password)
        return account_identity(account) if account is not None else None

    identity = await throttled_login(LOGIN_THROTTLE, form_data.username, check,
                                     address=client_address(request))
    if identity is None:
        # 401 envelope + WWW-Authenticate: Bearer (fastapi's register_api_error_handlers).
        raise UnauthorizedError("Incorrect user ID or password")

    access_token = issue_token(request, identity, expires_in=API_TOKEN_LIFETIME)
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserBase)
async def me(identity: Identity = Depends(get_current_identity)):
    """The signed-in account."""
    account = await USER_STORE.get(identity.subject)
    assert account is not None  # register_users only resolves existing accounts
    return user_out(account)
