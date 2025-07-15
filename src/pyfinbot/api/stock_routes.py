from __future__ import annotations

from typing import Union

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlmodel import paginate
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from ..models.stock_models import Stock
from ..schemas.stock_schemas import StockCreate, StockRead, StockUpdate
from ..db.session import get_session

router = APIRouter(prefix="/stocks", tags=["Stocks"])


async def _searchForStock(session, stock_id: Union[int, str]) -> Stock:
    """Search for a stock by ID or market:symbol format."""
    if isinstance(stock_id, int) or stock_id.isdigit():
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
async def list_stocks(session: AsyncSession = Depends(get_session)):
    return await paginate(session, Stock)


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
