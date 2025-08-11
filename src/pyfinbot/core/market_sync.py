
import asyncio
from datetime import datetime, UTC
from typing import Callable, Dict, Tuple, List

import pandas as pd
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..models.stock_models import Stock


ASX_CSV_URL = "https://asx.api.markitdigital.com/asx-research/1.0/companies/directory/file"


def fetchASXListed() -> Dict[str, str]:
    """
    Download the ASX-listed companies CSV and return a mapping
    { SYMBOL -> COMPANY NAME }.
    """
    df = pd.read_csv(ASX_CSV_URL, usecols=["ASX code", "Company name"])
    df.rename(columns={"ASX code": "symbol", "Company name": "name"}, inplace=True)
    df["symbol"] = df["symbol"].str.upper()
    return dict(zip(df["symbol"], df["name"]))


MARKET_FETCHERS = {
    "ASX": fetchASXListed,
}


async def syncMarket(session: AsyncSession, market: str, fetch_data: Callable = None) -> Tuple[List[str], List[str], List[str]]:
    """
    Upsert all Market tickers:
      - create new
      - update name if changed
      - soft‑archive those no longer listed
    Returns: (created, updated, archived) lists of symbols.
    """
    if fetch_data is None:
        fetch_data = MARKET_FETCHERS.get(market.upper())
        if fetch_data is None:
            raise ValueError(f"No fetcher available for market: {market}")

    name_map = await asyncio.to_thread(fetch_data)
    symbols = list(name_map.keys())

    # Load existing ASX stocks
    result = await session.exec(select(Stock).where(Stock.market == market.upper()))
    stocks = result.scalars().all()
    existing: Dict[str, Stock] = {s.symbol: s for s in stocks}

    created, updated, archived = [], [], []
    now = datetime.now()

    # Upsert records
    for sym in symbols:
        company_name = name_map[sym]

        if sym in existing:
            stock = existing[sym]
            # Name changed, or it was previously archived, reactivate/update
            if stock.name != company_name or not stock.is_active:
                stock.name = company_name
                stock.is_active = True
                stock.archived_at = None
                stock.write_datetime = now
                session.add(stock)
                updated.append(sym)
        else:
            new = Stock(
                symbol=sym,
                market=market.upper(),
                name=company_name
            )
            session.add(new)
            created.append(sym)

    # Archive delisted
    to_archive = set(existing) - set(symbols)
    for sym in to_archive:
        stock = existing[sym]
        if stock.is_active:
            stock.is_active = False
            stock.archived_at = now
            stock.write_datetime = now
            session.add(stock)
            archived.append(sym)

    await session.commit()
    return created, updated, archived
