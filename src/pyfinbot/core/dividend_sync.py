"""
Dividend history sync via yfinance, following the same registry + injectable-
fetcher + upsert pattern as core/market_sync.py.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Tuple

import yfinance as yf
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..models.dividend_models import Dividend
from ..models.stock_models import Stock

MARKET_TO_YF_SUFFIX = {
    "ASX": ".AX",
}


def fetchDividendsForSymbol(symbol: str, market: str) -> Dict[date, Decimal]:
    """
    Fetch full dividend history for one stock via yfinance.
    Returns { ex_date -> amount_per_share }.
    """
    suffix = MARKET_TO_YF_SUFFIX.get(market.upper())
    if suffix is None:
        raise ValueError(f"No yfinance mapping for market: {market}")
    ticker = yf.Ticker(f"{symbol.upper()}{suffix}")
    series = ticker.dividends
    return {ts.date(): Decimal(str(amt)) for ts, amt in series.items()}


async def syncDividends(
    session: AsyncSession,
    stock_ids: Optional[List[int]] = None,
    fetch_for_symbol: Callable[[str, str], Dict[date, Decimal]] = fetchDividendsForSymbol,
) -> Tuple[List[str], List[str], List[str]]:
    """
    Upsert Dividend rows for the given stock_ids (all Stock rows if None).
    Returns (created, updated, errors) — each a list of "MARKET:SYMBOL@ex_date"
    (or "MARKET:SYMBOL: detail" for errors) labels.
    """
    stmt = select(Stock)
    if stock_ids is not None:
        stmt = stmt.where(Stock.id.in_(stock_ids))
    result = await session.exec(stmt)
    stocks = result.all()

    created, updated, errors = [], [], []
    now = datetime.now()

    for stock in stocks:
        try:
            history = await asyncio.to_thread(fetch_for_symbol, stock.symbol, stock.market)
        except Exception as exc:
            errors.append(f"{stock.market}:{stock.symbol}: {exc}")
            continue

        existing_result = await session.exec(
            select(Dividend).where(Dividend.stock_id == stock.id)
        )
        existing: Dict[date, Dividend] = {d.ex_date: d for d in existing_result.all()}

        for ex_date, amount in history.items():
            if ex_date in existing:
                row = existing[ex_date]
                if row.amount_per_share != amount:
                    row.amount_per_share = amount
                    row.write_datetime = now
                    session.add(row)
                    updated.append(f"{stock.market}:{stock.symbol}@{ex_date}")
            else:
                session.add(Dividend(
                    stock_id=stock.id,
                    ex_date=ex_date,
                    amount_per_share=amount,
                    source="yfinance",
                ))
                created.append(f"{stock.market}:{stock.symbol}@{ex_date}")

    await session.commit()
    return created, updated, errors
