from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import SQLModel

from pyfinbot import models  # noqa: F401  # registers model tables on SQLModel.metadata


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
