from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from greentechhub_core.health import HealthResult
from greentechhub_core.sqlalchemy import Database
from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession
from sqlmodel.ext.asyncio.session import AsyncSession

from ..core.settings import settings

_PROJECT_ROOT = Path(__file__).resolve().parents[3]

# The app's engine and sessions, built on first use (greentechhub-core's
# Database). Sessions are SQLModel's; session_factory() gives plain
# SQLAlchemy ones.
db = Database(settings.ASYNC_DATABASE_URL, echo=settings.DB_ECHO, session_class=AsyncSession)

_MIGRATIONS = {
    "alembic_ini": _PROJECT_ROOT / "alembic.ini",
    "script_location": _PROJECT_ROOT / "src" / "pyfinbot" / "alembic",
    "project_root": _PROJECT_ROOT,
}


def _run_migrations() -> None:
    # Absolute paths, so startup works whatever the CWD; alembic/env.py
    # keeps the app's JSON logging (configure_logger=False).
    db.migrate(**_MIGRATIONS)


async def init_db():
    await db.migrate_async(**_MIGRATIONS)


async def get_session() -> AsyncGenerator[Any, Any]:
    async for session in db.session():
        yield session


def get_session_factory() -> Any:
    """The async sessionmaker code outside a request uses — e.g. the
    greentechhub settings store, which opens its own sessions rather than
    going through get_session. A test override wins (set_session_factory_
    override), else the lazily built one from ASYNC_DATABASE_URL."""
    return db.sessionmaker()


def set_session_factory_override(factory: Optional[Any]) -> None:
    """Point sessions at another sessionmaker (tests bind one to their
    per-test connection), or back to the real one with None."""
    db.override(factory)


def session_factory() -> SAAsyncSession:
    """A new plain SQLAlchemy session on the current sessionmaker's bind:
    the shape SQLAlchemySettingsStore(async_session_factory=...) takes."""
    return db.session_factory()


async def database_ready() -> HealthResult:
    """/health/ready's database check: SELECT 1 through the bind sessions
    come from (follows a test override)."""
    return await db.ready()
