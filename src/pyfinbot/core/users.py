"""Password users: the one place a User is created, its password set, and a
sign-in checked (bcrypt via greentechhub_core.security). Used by the web
sign-in and Settings › Password, the API's token login and user routes,
scripts/create_user.py and the demo seed."""

from datetime import datetime, timezone
from typing import Optional

from greentechhub_core.security import hash_password, verify_password
from sqlmodel.ext.asyncio.session import AsyncSession

from ..models.user_models import User


def new_user(user_id: str, password: str) -> User:
    """An active User with `password` hashed; not added to a session."""
    return User(id=user_id, active=True, password_hash=hash_password(password))


def set_password(user: User, password: str) -> None:
    """Store `password`'s hash on `user` and touch write_datetime; the
    caller adds and commits."""
    user.password_hash = hash_password(password)
    user.write_datetime = datetime.now(timezone.utc)


def password_matches(user: Optional[User], password: str) -> bool:
    """Whether `user` exists, has a password and it's `password`."""
    return bool(user and user.password_hash and verify_password(password, user.password_hash))


async def check_password(session: AsyncSession, user_id: str, password: str) -> Optional[User]:
    """The User if `password` is theirs, else None (unknown id, no password
    set, or wrong password: all the same to the caller)."""
    user = await session.get(User, user_id)
    return user if password_matches(user, password) else None
