from __future__ import annotations

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..models.user_models import User
from ..schemas.user_schemas import UserBase, UserCreate
from ..db.session import get_session

router = APIRouter(prefix="/users", tags=["Users"])

# --- API Routes ---

@router.post("/", response_model=UserBase)
async def create_user(user_in: UserCreate, session: AsyncSession = Depends(get_session)):
    # Check if user already exists
    existing_user = await session.exec(
        select(User).where(User.external_id == user_in.external_id)
    )
    if existing_user.first():
        raise HTTPException(status_code=400, detail="User already registered")

    # Create new user object
    new_user = User(
        external_id=user_in.external_id,
        active=True,
    )
    session.add(new_user)

    try:
        await session.commit()
        await session.refresh(new_user)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Failed to create user")

    return new_user


@router.get("/", response_model=list[UserBase])
async def list_users(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(User))
    return result.all()


@router.get("/{user_id}", response_model=UserBase)
async def get_user(user_id: int, session: AsyncSession = Depends(get_session)):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/{user_id}", response_model=UserBase)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    session: AsyncSession = Depends(get_session)
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_update.name is not None:
        user.name = user_update.name
    if user_update.password is not None:
        user.password_hash = bcrypt.hashpw(user_update.password.encode(), bcrypt.gensalt()).decode()
    if user_update.is_active is not None:
        user.is_active = user_update.is_active

    session.add(user)
    try:
        await session.commit()
        await session.refresh(user)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Failed to update user")

    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, session: AsyncSession = Depends(get_session)):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await session.delete(user)
    await session.commit()
