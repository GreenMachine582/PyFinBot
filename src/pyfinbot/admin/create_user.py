"""Create a user from the shell — how a deployment gets its first user, now
that POST /api/users/ needs users.manage (no open registration):

    python scripts/create_user.py alice        # prompts for the password twice
    python scripts/create_user.py alice --email alice@example.com

Then make them the first admin with ROLE_BOOTSTRAP=alice=admin (bootstrap
entries match the username); after that, admins create users through the
API and assign roles at /admin/roles. Works in any ENVIRONMENT. Behind
Authentik (AUTH_ADAPTER=forward_auth) accounts are created on first sign-in
instead, and this is only for the local break-glass login.
"""

import argparse
import asyncio
import getpass
import sys
from typing import Optional, Sequence

from greentechhub_core.users import UserAccount, UserExists

from ..core.users import create_account

__all__ = ["UserExists", "create_user", "main"]


async def create_user(username: str, password: str, *, email: Optional[str] = None,
                      display_name: Optional[str] = None) -> UserAccount:
    """Create an active account with a bcrypt-hashed password. Raises
    UserExists for a taken username or email, ValueError for a blank
    username/password or a malformed email."""
    return await create_account(username, password, email=email, display_name=display_name)


async def _run(username: str, password: str, email: Optional[str]) -> UserAccount:
    from ..db.session import init_db

    await init_db()
    return await create_user(username, password, email=email)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Create a PyFinBot user.")
    parser.add_argument("username", help="the login name")
    parser.add_argument("--email", default=None, help="their email address (optional)")
    args = parser.parse_args(argv)
    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Repeat password: "):
        print("The passwords don't match.", file=sys.stderr)
        return 1
    try:
        account = asyncio.run(_run(args.username, password, args.email))
    except ValueError as exc:
        print(f"Not created: {exc}.", file=sys.stderr)
        return 1
    print(f"Created {account.username!r} (id {account.id}). To make them an admin, set "
          f"ROLE_BOOTSTRAP={account.username}=admin (or assign the role at /admin/roles as another admin).")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
