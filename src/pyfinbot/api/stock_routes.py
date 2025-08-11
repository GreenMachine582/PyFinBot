from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlmodel import paginate
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..core.market_sync import syncMarket, MARKET_FETCHERS
from ..core.sorting import buildSortOrderBy
from ..core.sa_filters_compat import buildWhereFromSAFSpec
from ..models.stock_models import Stock
from ..schemas.stock_schemas import StockCreate, StockRead, StockUpdate, SyncResult
from ..db.session import get_session

router = APIRouter(prefix="/stocks", tags=["Stocks"])

# Allowed field map (external -> model attribute). Add more as needed.
ALLOWED_FILTERING_FIELDS = {
    "id": "id",
    "market": "market",
    "symbol": "symbol",
    "name": "name",
    "is_active": "is_active",
}


async def _searchForStock(session: AsyncSession, stock_id: int | str) -> Optional[Stock]:
    """Search for a stock by ID or market:symbol format."""
    if isinstance(stock_id, int) or (isinstance(stock_id, str) and stock_id.isdigit()):
        return await session.get(Stock, int(stock_id))
    try:
        market, symbol = stock_id.split(":")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid stock identifier format. Use 'MARKET:SYMBOL'."
        )
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stock already registered")

    session.add(new_stock)
    try:
        await session.commit()
        await session.refresh(new_stock)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create stock")

    return new_stock


@router.get("/", response_model=Page[StockRead])
async def list_stocks(
    session: AsyncSession = Depends(get_session),

    # Complex filters: sqlalchemy-filters schema (JSON string)
    filters: Optional[str] = Query(None, description="sqlalchemy-filters JSON spec"),

    # Tabulator sends sorters as JSON list; keep 'sort' too for compatibility
    sorters: Optional[str] = Query(None, description="Tabulator sorters JSON"),
    sort: Optional[str] = Query("market,symbol", description="Comma list of fields, '-' for desc"),
):
    stmt = select(Stock)

    # Build WHERE from sqlalchemy-filters spec
    if filters:
        try:
            filters_spec = json.loads(filters)
        except json.JSONDecodeError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid 'filters' JSON")

        where_expr = buildWhereFromSAFSpec(model=Stock, spec=filters_spec, allowed_fields=ALLOWED_FILTERING_FIELDS)
        if where_expr is not None:
            stmt = stmt.where(where_expr)

    # Sorting (Tabulator sorters > fallback 'sort')
    order_by = buildSortOrderBy(Stock, ALLOWED_FILTERING_FIELDS, sorters, sort)
    if order_by:
        stmt = stmt.order_by(*order_by)

    # Let fastapi_pagination handle page/size params
    return await paginate(session, stmt)


@router.get("/{stock_id}", response_model=StockRead)
async def get_stock(stock_id: Union[int, str], session: AsyncSession = Depends(get_session)):
    stock = await _searchForStock(session, stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    return stock


@router.put("/{stock_id}", response_model=StockRead)
async def update_stock(
    stock_id: Union[int, str],
    stock_update: StockUpdate,
    session: AsyncSession = Depends(get_session)
):
    stock = await _searchForStock(session, stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    for key, value in stock_update.model_dump(exclude_unset=True).items():
        setattr(stock, key, value)

    # Set archive_at when not provided
    if not stock.is_active and not stock.archive_at:
        stock.archive_at = datetime.now(timezone.utc)

    session.add(stock)
    try:
        await session.commit()
        await session.refresh(stock)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Failed to update stock")

    return stock


@router.delete("/{stock_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stock(stock_id: Union[int, str], session: AsyncSession = Depends(get_session)):
    stock = await _searchForStock(session, stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

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

    if m in MARKET_FETCHERS:
        created, updated, archived = await syncMarket(session, "ASX")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sync for market '{market}' is not supported"
        )

    return SyncResult(
        created=created,
        updated=updated,
        archived=archived
    )
