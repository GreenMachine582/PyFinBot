import asyncio
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
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
    command.upgrade(cfg, "head")


async def init_db():
    await asyncio.to_thread(_run_migrations)


async def get_session() -> AsyncGenerator[Any, Any]:
    _, session_maker = _get_engine()
    async with session_maker() as session:
        yield session
