from typing import Any

from greentechhub_core.query.types import Page
from greentechhub_fastapi.query import PageParams, page_params
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

PAGE_SIZE = 50

# page/size for the web tables' "load more" rows; next_page_url (same module
# in greentechhub_fastapi.query) builds the link.
web_page_params = page_params(default_size=PAGE_SIZE)


async def paginate(session: AsyncSession, stmt: Any, params: PageParams) -> Page:
    """Count + offset/limit an async SQLAlchemy select into a greentechhub_core
    Page. Stays here rather than in greentechhub-fastapi: neither shared
    package depends on SQLAlchemy (BottleBot pages in Python instead)."""
    total = (await session.exec(select(func.count()).select_from(stmt.order_by(None).subquery()))).one()
    offset = (params.page - 1) * params.size
    items = list((await session.exec(stmt.offset(offset).limit(params.size))).all())
    return Page(items=items, total=total, page=params.page, size=params.size)
