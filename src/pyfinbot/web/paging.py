from typing import Any

from greentechhub_ui import TableState
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

PAGE_SIZE = 50
PAGE_SIZES = (10, 25, PAGE_SIZE)


def sort_string(state: TableState, *tiebreakers: str) -> str:
    """A TableState's sort as core.sorting's "-field,other" string, with
    tie-breakers (in the same direction) so paging is stable."""
    prefix = "-" if state.direction == "desc" else ""
    return ",".join(prefix + field for field in (state.sort, *tiebreakers) if field)


async def paginate(session: AsyncSession, stmt: Any, state: TableState) -> tuple[list, TableState]:
    """Count + offset/limit an async SQLAlchemy select for a gth_data_table:
    the page's rows and the state with its total. Stays here rather than in
    greentechhub-fastapi: neither shared package depends on SQLAlchemy
    (BottleBot pages in Python instead)."""
    total = (await session.exec(select(func.count()).select_from(stmt.order_by(None).subquery()))).one()
    items = list((await session.exec(stmt.offset(state.offset).limit(state.limit))).all())
    return items, state.with_result(total=total)
