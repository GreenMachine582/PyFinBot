from __future__ import annotations

import pytest
from greentechhub_fastapi import testing as gth_testing
from greentechhub_fastapi.testing import hx_triggers, post_login  # noqa: F401  # re-exported for tests
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import SQLModel

from pyfinbot import models  # noqa: F401  # registers model tables on SQLModel.metadata

# greentechhub-fastapi's HTTP fixtures (gth_client, client_as) on top of
# greentechhub-core's database ones (gth_session, gth_connection, ...): every
# test runs inside a rolled-back transaction, and the app's sessions join it.
pytest_plugins = ["greentechhub_fastapi.testing"]

PASSWORD = "hunter2!"


@pytest.fixture(scope="session")
def gth_metadata():
    return SQLModel.metadata


@pytest.fixture(scope="session")
def gth_session_class():
    return AsyncSession


@pytest.fixture
def gth_app():
    from pyfinbot.pyfinbot import app

    return app


@pytest.fixture
def gth_db():
    from pyfinbot.db.session import db

    return db


@pytest.fixture
def gth_create_user():
    return _create_user


async def _create_user(username: str, password: str = PASSWORD) -> str:
    """Create a user account in the test database (USER_STORE's sessions
    come from db.session.session_factory, which gth_db points at the test
    connection) and return its id — the subject every route keys on.
    There's no open registration (POST /api/users/ needs users.manage), so
    tests seed users the way scripts/create_user.py does."""
    from pyfinbot.admin.create_user import create_user as _create

    return (await _create(username, password)).id


async def create_user(client: AsyncClient, username: str, password: str = PASSWORD) -> str:
    """_create_user for tests that have a client in hand; the account id."""
    return await _create_user(username, password)


async def user_id(username: str) -> str:
    """The account id of the user signed in as `username`."""
    from pyfinbot.core.users import USER_STORE

    account = await USER_STORE.by_username(username)
    assert account is not None, f"no user {username!r}"
    return account.id


async def insert_account(session: AsyncSession, username: str, *,
                         password_hash: str | None = None) -> str:
    """Insert a gth_users row straight into `session` (for a row the store
    would refuse to write, e.g. a malformed hash); its account id."""
    from datetime import UTC, datetime

    from greentechhub_core.users import new_account

    from pyfinbot.models.settings_models import USERS_TABLE

    account = new_account(username, now=datetime.now(UTC), password_hash=password_hash)
    await session.execute(USERS_TABLE.insert().values(
        {column.name: getattr(account, column.name) for column in USERS_TABLE.columns}))
    return account.id


async def account_row(session: AsyncSession, username: str):
    """The gth_users row for `username`, read in `session`, or None."""
    from sqlalchemy import select

    from pyfinbot.models.settings_models import USERS_TABLE

    result = await session.execute(select(USERS_TABLE).where(USERS_TABLE.c.username == username))
    return result.first()


async def make_admin(client: AsyncClient, username: str) -> None:
    """Grant `username`'s account the admin role, as /admin/roles would. The
    grant store uses db.session.session_factory, which gth_db points at the
    test connection."""
    from greentechhub_fastapi.permissions import GRANTS_STATE_KEY

    from pyfinbot.core.permissions import ADMIN
    from pyfinbot.pyfinbot import app

    await getattr(app.state, GRANTS_STATE_KEY).assign(await user_id(username), ADMIN.name)


async def register_and_login(client: AsyncClient, username: str, password: str = PASSWORD) -> dict[str, str]:
    """Create a user (username + password) and log in, returning an Authorisation header dict."""
    await create_user(client, username, password)

    resp = await client.post(
        "/api/auth/login", data={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def web_login(client: AsyncClient, username: str, password: str = PASSWORD) -> None:
    """Create a user and sign in through the web form (greentechhub-fastapi's
    web_login), leaving the gth_session cookie on `client`. Calling it again
    for another user switches the client to that user.

    It then sends the gth_csrf cookie's token as X-CSRF-Token on every
    request, as the app shell's hx-headers does in a browser."""
    await create_user(client, username, password)
    await gth_testing.web_login(client, username, password)
    send_csrf(client)


def send_csrf(client: AsyncClient) -> None:
    """Send the client's gth_csrf token as X-CSRF-Token on every request
    from now on, as the app shell's hx-headers does. The token comes from
    the cookie re-set without Secure (domain ""), else a response's, which
    is re-set without Secure here so it goes back over the tests' http://."""
    jar = client.cookies
    token = jar.get("gth_csrf", domain="")
    if token is None:
        token = next(cookie.value for cookie in jar.jar if cookie.name == "gth_csrf")
        jar.set("gth_csrf", token)
    client.headers["X-CSRF-Token"] = token


async def create_stock(client: AsyncClient, symbol: str = "BHP", market: str = "ASX",
                       name: str = "BHP Group") -> dict:
    """Create a stock through the API (no auth needed) and return its JSON."""
    resp = await client.post("/api/stocks/", json={"symbol": symbol, "market": market, "name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()
