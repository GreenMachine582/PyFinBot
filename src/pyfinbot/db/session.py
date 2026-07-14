from typing import Any, AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from ..core.settings import settings

_engine: Optional[AsyncEngine] = None
_session_maker = None


def _get_engine():
    global _engine, _session_maker
    if _engine is None:
        url = settings.ASYNC_DATABASE_URL
        if not url:
            raise RuntimeError("ASYNC_DATABASE_URL is not configured")
        _engine = create_async_engine(url, echo=True)
        _session_maker = sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _engine, _session_maker


async def init_db():
    engine, _ = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncGenerator[Any, Any]:
    _, session_maker = _get_engine()
    async with session_maker() as session:
        yield session
