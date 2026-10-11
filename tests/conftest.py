from __future__ import annotations

import json

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import SQLModel

from pyfinbot import models  # noqa: F401  # registers model tables on SQLModel.metadata

# greentechhub-core's database fixtures: gth_session, gth_connection,
# gth_sessionmaker and gth_database, each test inside a rolled-back transaction.
pytest_plugins = ["greentechhub_core.testing.sqlalchemy"]


@pytest.fixture(scope="session")
def gth_metadata():
    return SQLModel.metadata


@pytest.fixture(scope="session")
def gth_session_class():
    return AsyncSession


@pytest_asyncio.fixture(autouse=True)
async def _ensure_auth_registered():
    """The `client` fixture clears every app.dependency_overrides entry at
    teardown — including the one register_auth(app, settings) installs at
    pyfinbot.py's module-import time (which only happens once per test
    session). After the first test using `client` tears down, every
    subsequent test would hit the unregistered get_current_user
    placeholder's NotImplementedError instead of the real local adapter.
    Re-applying it before each test (idempotent — just re-sets the same
    dict entry) avoids that ordering trap.

    It uses the settings object pyfinbot.py was built with, not a fresh
    import of core.settings: test_settings reloads that module, and without
    a SECRET_KEY (CI has no .env) the reload draws a new random key — which
    would no longer match the one the login routes sign sessions with."""
    from greentechhub_fastapi import register_auth

    from pyfinbot import pyfinbot as app_module

    register_auth(app_module.app, app_module.settings)


@pytest_asyncio.fixture
async def client(gth_database):
    from pyfinbot.db.session import db
    from pyfinbot.pyfinbot import app

    # Every session the app opens (get_session, the settings and grant
    # stores, the readiness check) comes from db, so they all join the test's
    # rolled-back transaction.
    with gth_database(db), patch("pyfinbot.pyfinbot.init_db", new=AsyncMock()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c

    app.dependency_overrides.clear()


async def create_user(client: AsyncClient, user_id: str, password: str = "hunter2!") -> None:
    """Create a user directly in the test database, through the same
    get_session override the app's routes use. There's no open registration
    any more (POST /api/users/ needs users.manage), so tests seed users the
    way scripts/create_user.py does."""
    from greentechhub_fastapi.auth import resolve_dependency

    from pyfinbot.admin.create_user import create_user as _create
    from pyfinbot.db.session import get_session
    from pyfinbot.pyfinbot import app

    async with resolve_dependency(app, get_session) as session:
        await _create(session, user_id, password)


async def make_admin(client: AsyncClient, user_id: str) -> None:
    """Grant `user_id` the admin role, as /admin/roles would. The grant
    store uses db.session.session_factory, which follows the client
    fixture's gth_database(db) to the test connection."""
    from greentechhub_fastapi.permissions import GRANTS_STATE_KEY

    from pyfinbot.core.permissions import ADMIN
    from pyfinbot.pyfinbot import app

    await getattr(app.state, GRANTS_STATE_KEY).assign(user_id, ADMIN.name)


async def register_and_login(client: AsyncClient, user_id: str, password: str = "hunter2!") -> dict[str, str]:
    """Create a user (id + password) and log in, returning an Authorisation header dict."""
    await create_user(client, user_id, password)

    resp = await client.post(
        "/api/auth/login", data={"username": user_id, "password": password}
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def post_login(client: AsyncClient, user_id: str, password: str, **kwargs):
    """POST the web sign-in form the way a browser would, CSRF token
    included: GET /login first for the gth_csrf cookie, then send it back
    with the same token as the form's csrf_token field. The cookie is marked
    Secure, so it's re-set without that flag for the tests' http:// base URL
    (as web_login does for gth_session). kwargs go to client.post."""
    page = await client.get("/login", headers={"Accept": "text/html"})
    token = page.cookies["gth_csrf"]
    client.cookies.set("gth_csrf", token)
    data = {"user_id": user_id, "password": password, "csrf_token": token}
    return await client.post("/login", data=data, **kwargs)


async def web_login(client: AsyncClient, user_id: str, password: str = "hunter2!") -> None:
    """Register a user and log in through the web form, leaving the
    gth_session cookie on `client` for subsequent page requests. Calling
    it again for another user switches the client to that user.

    The cookie is marked Secure, so httpx's jar won't send it back over the
    tests' http:// base URL on its own — it's re-set without that flag."""
    await create_user(client, user_id, password)
    resp = await post_login(client, user_id, password, follow_redirects=False)
    assert resp.status_code == 303, resp.text
    client.cookies.set("gth_session", resp.cookies["gth_session"])


async def create_stock(client: AsyncClient, symbol: str = "BHP", market: str = "ASX",
                       name: str = "BHP Group") -> dict:
    """Create a stock through the API (no auth needed) and return its JSON."""
    resp = await client.post("/api/stocks/", json={"symbol": symbol, "market": market, "name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()


def hx_triggers(resp) -> dict:
    """The parsed HX-Trigger header of a web route's response."""
    return json.loads(resp.headers["HX-Trigger"])
