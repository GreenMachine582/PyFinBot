"""Create a user from the shell — how a deployment gets its first user, now
that POST /api/users/ needs users.manage (no open registration):

    python scripts/create_user.py alice        # prompts for the password twice

Then make them the first admin with ROLE_BOOTSTRAP=alice=admin; after that,
admins create users through the API and assign roles at /admin/roles.
Works in any ENVIRONMENT.
"""

import argparse
import asyncio
import getpass
import sys
from typing import Optional, Sequence

from sqlmodel.ext.asyncio.session import AsyncSession

from ..core.users import new_user
from ..models.user_models import User


class UserExists(ValueError):
    pass


async def create_user(session: AsyncSession, user_id: str, password: str) -> User:
    """Create an active user with a bcrypt-hashed password and commit.
    Raises UserExists for a taken id, ValueError for a blank id/password."""
    user_id = user_id.strip()
    if not user_id or not password:
        raise ValueError("a user id and a password are required")
    if await session.get(User, user_id):
        raise UserExists(f"user {user_id!r} already exists")
    user = new_user(user_id, password)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _run(user_id: str, password: str) -> None:
    from ..db.session import _get_engine, init_db

    await init_db()
    _, session_maker = _get_engine()
    async with session_maker() as session:
        await create_user(session, user_id, password)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Create a PyFinBot user.")
    parser.add_argument("user_id", help="the login id")
    args = parser.parse_args(argv)
    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Repeat password: "):
        print("The passwords don't match.", file=sys.stderr)
        return 1
    try:
        asyncio.run(_run(args.user_id, password))
    except ValueError as exc:
        print(f"Not created: {exc}.", file=sys.stderr)
        return 1
    print(f"Created {args.user_id!r}. To make them an admin, set ROLE_BOOTSTRAP={args.user_id}=admin "
          "(or assign the role at /admin/roles as another admin).")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
