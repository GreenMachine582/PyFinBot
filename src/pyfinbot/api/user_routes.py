from __future__ import annotations

from fastapi import APIRouter, Depends, status
from greentechhub_core.security import hash_password
from greentechhub_core.types import BadRequestError, ForbiddenError, NotFoundError
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..core.dependencies import get_current_user, require_api_permission
from ..core.permissions import USERS_MANAGE
from ..models.user_models import User
from ..schemas.user_schemas import UserBase, UserCreate, UserUpdate
from ..db.session import get_session

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/", response_model=UserBase, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_api_permission(USERS_MANAGE)),
):
    """Create a user (users.manage only: there's no open registration — the
    first user comes from scripts/create_user.py plus ROLE_BOOTSTRAP)."""
    if await session.get(User, user_in.id):
        raise BadRequestError("User already registered", code="user_exists")

    new_user = User(id=user_in.id, active=True, password_hash=hash_password(user_in.password))
    session.add(new_user)
    try:
        await session.commit()
        await session.refresh(new_user)
    except IntegrityError:
        await session.rollback()
        raise BadRequestError("Failed to create user", code="create_failed")

    return new_user


@router.get("/", response_model=list[UserBase])
async def list_users(
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_api_permission(USERS_MANAGE)),
):
    """Every user (users.manage only)."""
    result = await session.exec(select(User))
    return result.all()


@router.get("/{user_id}", response_model=UserBase)
async def get_user(
    user_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id:
        raise ForbiddenError("Not allowed to access this user")

    user = await session.get(User, user_id)
    if not user:
        raise NotFoundError("User not found")
    return user


@router.put("/{user_id}", response_model=UserBase)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id:
        raise ForbiddenError("Not allowed to modify this user")

    user = await session.get(User, user_id)
    if not user:
        raise NotFoundError("User not found")

    update_data = user_update.model_dump(exclude_unset=True)
    password = update_data.pop("password", None)
    if password is not None:
        user.password_hash = hash_password(password)
    for key, value in update_data.items():
        setattr(user, key, value)

    session.add(user)
    try:
        await session.commit()
        await session.refresh(user)
    except IntegrityError:
        await session.rollback()
        raise BadRequestError("Failed to update user", code="update_failed")

    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id:
        raise ForbiddenError("Not allowed to delete this user")

    user = await session.get(User, user_id)
    if not user:
        raise NotFoundError("User not found")

    await session.delete(user)
    await session.commit()
