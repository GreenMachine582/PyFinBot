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


async def _create_user(user_id: str, password: str = PASSWORD) -> None:
    """Create a user directly in the test database, through the app's
    get_session (which gth_db points at the test connection). There's no
    open registration any more (POST /api/users/ needs users.manage), so
    tests seed users the way scripts/create_user.py does."""
    from greentechhub_fastapi.auth import resolve_dependency

    from pyfinbot.admin.create_user import create_user as _create
    from pyfinbot.db.session import get_session
    from pyfinbot.pyfinbot import app

    async with resolve_dependency(app, get_session) as session:
        await _create(session, user_id, password)


async def create_user(client: AsyncClient, user_id: str, password: str = PASSWORD) -> None:
    """_create_user for tests that have a client in hand."""
    await _create_user(user_id, password)


async def make_admin(client: AsyncClient, user_id: str) -> None:
    """Grant `user_id` the admin role, as /admin/roles would. The grant
    store uses db.session.session_factory, which gth_db points at the test
    connection."""
    from greentechhub_fastapi.permissions import GRANTS_STATE_KEY

    from pyfinbot.core.permissions import ADMIN
    from pyfinbot.pyfinbot import app

    await getattr(app.state, GRANTS_STATE_KEY).assign(user_id, ADMIN.name)


async def register_and_login(client: AsyncClient, user_id: str, password: str = PASSWORD) -> dict[str, str]:
    """Create a user (id + password) and log in, returning an Authorisation header dict."""
    await create_user(client, user_id, password)

    resp = await client.post(
        "/api/auth/login", data={"username": user_id, "password": password}
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def web_login(client: AsyncClient, user_id: str, password: str = PASSWORD) -> None:
    """Create a user and sign in through the web form (greentechhub-fastapi's
    web_login), leaving the gth_session cookie on `client`. Calling it again
    for another user switches the client to that user."""
    await create_user(client, user_id, password)
    await gth_testing.web_login(client, user_id, password)


async def create_stock(client: AsyncClient, symbol: str = "BHP", market: str = "ASX",
                       name: str = "BHP Group") -> dict:
    """Create a stock through the API (no auth needed) and return its JSON."""
    resp = await client.post("/api/stocks/", json={"symbol": symbol, "market": market, "name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()
