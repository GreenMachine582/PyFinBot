import asyncio
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from alembic import command
from alembic.config import Config
from greentechhub_core.health import HealthResult
from greentechhub_core.health.checks import check_database
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from ..core.settings import settings

_engine: Optional[AsyncEngine] = None
_session_maker = None

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _get_engine():
    global _engine, _session_maker
    if _engine is None:
        url = settings.ASYNC_DATABASE_URL
        if not url:
            raise RuntimeError("ASYNC_DATABASE_URL is not configured")
        _engine = create_async_engine(url, echo=settings.DB_ECHO)
        _session_maker = sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _engine, _session_maker


def _run_migrations() -> None:
    # script_location/prepend_sys_path in alembic.ini are relative to the
    # process's CWD, which the documented CLI workflow always runs from the
    # project root. Override both with absolute paths here so startup works
    # regardless of the CWD the app itself was launched from.
    cfg = Config(str(_PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_PROJECT_ROOT / "src" / "pyfinbot" / "alembic"))
    cfg.set_main_option("prepend_sys_path", str(_PROJECT_ROOT))
    # Keep the app's JSON logging: alembic/env.py skips alembic.ini's
    # fileConfig when told it isn't the CLI.
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")


async def init_db():
    await asyncio.to_thread(_run_migrations)


async def get_session() -> AsyncGenerator[Any, Any]:
    _, session_maker = _get_engine()
    async with session_maker() as session:
        yield session


_session_factory_override: Optional[Any] = None


def get_session_factory() -> Any:
    """The async sessionmaker code outside a request uses — e.g. the
    greentechhub settings store, which opens its own sessions rather than
    going through get_session. A test override wins (set_session_factory_
    override), else the lazily built one from ASYNC_DATABASE_URL."""
    if _session_factory_override is not None:
        return _session_factory_override
    _, session_maker = _get_engine()
    return session_maker


def set_session_factory_override(factory: Optional[Any]) -> None:
    """Point get_session_factory at another sessionmaker (tests bind one to
    their per-test connection), or back to the real one with None."""
    global _session_factory_override
    _session_factory_override = factory


def session_factory() -> SAAsyncSession:
    """A new session on get_session_factory()'s bind and options, looked up
    per call: the shape SQLAlchemySettingsStore(async_session_factory=...)
    takes, without creating the engine at import time. A plain SQLAlchemy
    AsyncSession, since the store is plain SQLAlchemy (SQLModel's session
    would flag its session.execute() calls as deprecated)."""
    return SAAsyncSession(**get_session_factory().kw)


async def database_ready() -> HealthResult:
    """/health/ready's database check: greentechhub-core's check_database
    (SELECT 1) against the engine sessions come from. Looked up per call, so
    it follows a test override; a connection-bound override uses its engine."""
    bind = get_session_factory().kw["bind"]
    return await check_database(bind if hasattr(bind, "connect") else bind.engine)
