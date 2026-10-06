"""core/users.py (todo › Lean now): the one place a password user is created,
its password set and a sign-in checked."""
from datetime import datetime, timedelta, timezone

from greentechhub_core.security import verify_password
from sqlmodel.ext.asyncio.session import AsyncSession

from pyfinbot.core.users import check_password, new_user, password_matches, set_password
from pyfinbot.models.user_models import User


def test_new_user_is_active_with_a_hashed_password():
    user = new_user("users-a", "s3cret-pass")
    assert user.id == "users-a" and user.active
    assert user.password_hash and user.password_hash != "s3cret-pass"
    assert verify_password("s3cret-pass", user.password_hash)


def test_set_password_rehashes_and_touches_write_datetime():
    user = new_user("users-b", "old-pass-1")
    user.write_datetime = datetime.now(timezone.utc) - timedelta(days=1)
    before = user.write_datetime
    set_password(user, "new-pass-2")
    assert verify_password("new-pass-2", user.password_hash or "")
    assert not verify_password("old-pass-1", user.password_hash or "")
    assert user.write_datetime > before


def test_password_matches_needs_a_user_with_a_password():
    assert not password_matches(None, "x")
    assert not password_matches(User(id="users-c", active=True, password_hash=None), "x")
    assert password_matches(new_user("users-c", "right-pass"), "right-pass")


async def test_check_password(session: AsyncSession):
    session.add(new_user("users-d", "right-pass"))
    session.add(User(id="users-e", active=True, password_hash=None))
    await session.commit()

    assert (await check_password(session, "users-d", "right-pass")).id == "users-d"
    assert await check_password(session, "users-d", "wrong-pass") is None
    assert await check_password(session, "users-e", "anything") is None  # no password set
    assert await check_password(session, "nobody", "right-pass") is None
