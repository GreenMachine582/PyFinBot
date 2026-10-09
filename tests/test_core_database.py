"""The database through greentechhub-core's Database (v0.13): db/session.py
keeps its names as thin wrappers over it instead of hand-rolling the engine,
sessionmaker, test override, readiness check and migrations."""
from unittest.mock import AsyncMock, patch

import pytest
from greentechhub_core.sqlalchemy import Database
from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from pyfinbot.db import session as db_session


@pytest.fixture
def override(connection):
    maker = async_sessionmaker(bind=connection, class_=AsyncSession, expire_on_commit=False)
    db_session.set_session_factory_override(maker)
    yield maker
    db_session.set_session_factory_override(None)


def test_db_is_cores_database():
    assert isinstance(db_session.db, Database)


async def test_override_applies_to_every_session(override, connection):
    assert db_session.get_session_factory() is override
    async for s in db_session.get_session():
        assert isinstance(s, AsyncSession) and s.bind is connection
    plain = db_session.session_factory()
    assert type(plain) is SAAsyncSession and plain.bind is connection
    await plain.close()


async def test_ready_checks_the_overridden_bind(override):
    result = await db_session.database_ready()
    assert result.status == "healthy", result.detail


async def test_init_db_migrates_with_absolute_paths():
    with patch.object(db_session.db, "migrate_async", new=AsyncMock()) as migrate:
        await db_session.init_db()
    kwargs = migrate.await_args.kwargs
    assert all(p.is_absolute() for p in kwargs.values())
    assert kwargs["alembic_ini"].is_file() and kwargs["script_location"].is_dir()
