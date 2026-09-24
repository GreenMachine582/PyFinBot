from __future__ import annotations

import json

from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import SQLModel

from pyfinbot import models  # noqa: F401  # registers model tables on SQLModel.metadata


@pytest_asyncio.fixture(autouse=True)
async def _ensure_auth_registered():
    """The `client` fixture clears every app.dependency_overrides entry at
    teardown — including the one register_auth(app, settings) installs at
    pyfinbot.py's module-import time (which only happens once per test
    session). After the first test using `client` tears down, every
    subsequent test would hit the unregistered get_current_user
    placeholder's NotImplementedError instead of the real local adapter.
    Re-applying it before each test (idempotent — just re-sets the same
    dict entry) avoids that ordering trap."""
    from greentechhub_fastapi import register_auth

    from pyfinbot.core.settings import settings
    from pyfinbot.pyfinbot import app

    register_auth(app, settings)


@pytest_asyncio.fixture(scope="session")
async def engine(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("db")
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    _engine = create_async_engine(db_url)

    # pysqlite (via aiosqlite) autocommits outside of explicit DML transactions,
    # which breaks SAVEPOINT-based per-test rollback unless disabled like this.
    # https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#serializable-isolation-savepoints-transactional-ddl
    @event.listens_for(_engine.sync_engine, "connect")
    def _do_connect(dbapi_connection, connection_record):
        dbapi_connection.isolation_level = None

    @event.listens_for(_engine.sync_engine, "begin")
    def _do_begin(conn):
        conn.exec_driver_sql("BEGIN")

    async with _engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield _engine
    await _engine.dispose()


@pytest_asyncio.fixture
async def connection(engine):
    async with engine.connect() as conn:
        await conn.begin()
        try:
            yield conn
        finally:
            await conn.rollback()


@pytest_asyncio.fixture
async def session(connection):
    async with AsyncSession(bind=connection, join_transaction_mode="create_savepoint") as s:
        yield s


@pytest_asyncio.fixture
async def client(connection):
    from pyfinbot.pyfinbot import app
    from pyfinbot.db.session import get_session

    async def _get_session():
        async with AsyncSession(bind=connection, join_transaction_mode="create_savepoint") as s:
            yield s

    app.dependency_overrides[get_session] = _get_session

    with patch("pyfinbot.pyfinbot.init_db", new=AsyncMock()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c

    app.dependency_overrides.clear()


async def register_and_login(client: AsyncClient, user_id: str, password: str = "hunter2!") -> dict[str, str]:
    """Register a user (id + password) and log in, returning an Authorisation header dict."""
    resp = await client.post("/api/users/", json={"id": user_id, "password": password})
    assert resp.status_code == 201, resp.text

    resp = await client.post(
        "/api/auth/login", data={"username": user_id, "password": password}
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def web_login(client: AsyncClient, user_id: str, password: str = "hunter2!") -> None:
    """Register a user and log in through the web form, leaving the
    gth_session cookie on `client` for subsequent page requests. Calling
    it again for another user switches the client to that user.

    The cookie is marked Secure, so httpx's jar won't send it back over the
    tests' http:// base URL on its own — it's re-set without that flag."""
    resp = await client.post("/api/users/", json={"id": user_id, "password": password})
    assert resp.status_code == 201, resp.text
    resp = await client.post("/login", data={"user_id": user_id, "password": password}, follow_redirects=False)
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
