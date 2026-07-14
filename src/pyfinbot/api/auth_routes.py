"""
Login endpoint — issues JWT access tokens.

Note: there is no separate username/email field on User. The OAuth2
password form's "username" is the same string as User.id.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel.ext.asyncio.session import AsyncSession

from ..core.security import create_access_token, verify_password
from ..db.session import get_session
from ..models.user_models import User

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
):
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect user ID or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user = await session.get(User, form_data.username)
    if not user or not user.password_hash:
        raise unauthorized
    if not verify_password(form_data.password, user.password_hash):
        raise unauthorized

    access_token = create_access_token(data={"sub": user.id})
    return {"access_token": access_token, "token_type": "bearer"}
