from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Union

from fastapi import APIRouter, Depends, status
from fastapi_pagination import Page
from greentechhub_core.query.envelope import to_envelope
from greentechhub_core.query.types import Sort
from greentechhub_core.sqlalchemy.query import page
from greentechhub_core.types import BadRequestError, ConflictError, NotFoundError
from greentechhub_fastapi.query import PageParams
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..core.market_sync import syncMarket, MARKET_FETCHERS, market_sync_guard
from ..models.stock_models import Stock
from ..schemas.stock_schemas import StockCreate, StockRead, StockUpdate, SyncResult
from ..db.session import get_session
from .query import page_request

router = APIRouter(prefix="/stocks", tags=["Stocks"])

# What the list's `filters` and `sort` may name (public name -> column); the
# web table sorts through it too. Anything else is ignored.
ALLOWED_FIELDS = {
    "id": Stock.id,
    "market": Stock.market,
    "symbol": Stock.symbol,
    "name": Stock.name,
    "is_active": Stock.is_active,
}
DEFAULT_SORT = (Sort(field="market"), Sort(field="symbol"))


async def _searchForStock(session: AsyncSession, stock_id: int | str) -> Optional[Stock]:
    """Search for a stock by ID or market:symbol format."""
    if isinstance(stock_id, int) or (isinstance(stock_id, str) and stock_id.isdigit()):
        return await session.get(Stock, int(stock_id))
    try:
        market, symbol = stock_id.split(":")
    except ValueError:
        raise BadRequestError("Invalid stock identifier format. Use 'MARKET:SYMBOL'.", code="invalid_stock_id")
    return await Stock.search(session, market=market, symbol=symbol)


@router.post("/", response_model=StockRead, status_code=status.HTTP_201_CREATED)
async def create_stock(stock_in: StockCreate, session: AsyncSession = Depends(get_session)):
    new_stock = Stock(
        symbol=stock_in.symbol.upper(),
        market=stock_in.market.upper(),
        name=stock_in.name,
    )

    # Check if stock already exists
    if await _searchForStock(session, f"{new_stock.market}:{new_stock.symbol}"):
        raise BadRequestError("Stock already registered", code="stock_exists")

    session.add(new_stock)
    try:
        await session.commit()
        await session.refresh(new_stock)
    except IntegrityError:
        await session.rollback()
        raise BadRequestError("Failed to create stock", code="create_failed")

    return new_stock


@router.get("/", response_model=Page[StockRead])
async def list_stocks(
    session: AsyncSession = Depends(get_session),
    params: PageParams = Depends(),
):
    """List stocks: `page`/`size`, `sort` (default "market,symbol"), and
    `filters` / `filter` on the fields in ALLOWED_FIELDS (api/query.py)."""
    result = await page(session, select(Stock), page_request(params), ALLOWED_FIELDS,
                        default_sort=DEFAULT_SORT)
    return to_envelope(result)


@router.get("/{stock_id}", response_model=StockRead)
async def get_stock(stock_id: Union[int, str], session: AsyncSession = Depends(get_session)):
    stock = await _searchForStock(session, stock_id)
    if not stock:
        raise NotFoundError("Stock not found")
    return stock


@router.put("/{stock_id}", response_model=StockRead)
async def update_stock(
    stock_id: Union[int, str],
    stock_update: StockUpdate,
    session: AsyncSession = Depends(get_session)
):
    stock = await _searchForStock(session, stock_id)
    if not stock:
        raise NotFoundError("Stock not found")

    for key, value in stock_update.model_dump(exclude_unset=True).items():
        setattr(stock, key, value)

    if not stock.is_active and not stock.archived_at:
        stock.archived_at = datetime.now(timezone.utc)

    session.add(stock)
    try:
        await session.commit()
        await session.refresh(stock)
    except IntegrityError:
        await session.rollback()
        raise BadRequestError("Failed to update stock", code="update_failed")

    return stock


@router.delete("/{stock_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stock(stock_id: Union[int, str], session: AsyncSession = Depends(get_session)):
    stock = await _searchForStock(session, stock_id)
    if not stock:
        raise NotFoundError("Stock not found")

    await session.delete(stock)
    await session.commit()


@router.post(
    "/sync/{market}",
    response_model=SyncResult,
    status_code=status.HTTP_200_OK,
    summary="Sync all companies in a given market (e.g. ASX)"
)
async def sync_stocks_for_market(
    market: str,
    session: AsyncSession = Depends(get_session)
):
    """
    - MARKET = "ASX" will pull the official ASX-listed CSV
    (soft‑creates, updates names, archives delisted).
    """
    m = market.upper()

    if m not in MARKET_FETCHERS:
        raise BadRequestError(f"Sync for market '{market}' is not supported", code="unsupported_market")

    with market_sync_guard(m) as acquired:
        if not acquired:
            raise ConflictError(f"{m} sync is already running")
        created, updated, archived = await syncMarket(session, m)

    return SyncResult(
        created=created,
        updated=updated,
        archived=archived
    )
