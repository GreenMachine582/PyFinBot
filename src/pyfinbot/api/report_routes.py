"""
Reporting endpoints. The computations live in core/reports.py (shared with
the web Reports page).

GET /api/reports/holdings          — Units held per stock as of a given date.
GET /api/reports/capital-gains     — Realised gain/loss for a fiscal year.

Both take `method`: average (the default) or fifo.
GET /api/reports/dividends         — Dividend income, optionally for one fiscal year.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from ..core import reports
from ..core.dependencies import get_current_user
from ..db.session import get_session
from ..models.user_models import User
from ..schemas.report_schemas import CapitalGainsReport, CostMethod, DividendsReport, HoldingsReport

router = APIRouter(prefix="/reports", tags=["Reports"])

METHOD_QUERY = Query(default=CostMethod.AVERAGE,
                     description="Cost basis: average (weighted average buy price) or fifo (first in, first out)")


@router.get("/holdings", response_model=HoldingsReport)
async def get_holdings(
    as_of: Optional[date] = Query(default=None, description="Snapshot date (default: today)"),
    method: CostMethod = METHOD_QUERY,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Return all stocks with a positive unit balance as of `as_of` date.

    Units held = sum(BUY units) - sum(SELL units) for transactions up to and
    including `as_of`. The cost basis per unit is the weighted average buy
    price across all qualifying buy transactions, or under `fifo`, that of the
    parcels still held.
    """
    return await reports.holdings_report(session, current_user.id, as_of or date.today(), method)


@router.get("/capital-gains", response_model=CapitalGainsReport)
async def get_capital_gains(
    fy: int = Query(..., description="AU fiscal year (e.g. 2024 = FY ending 30 Jun 2025)"),
    method: CostMethod = METHOD_QUERY,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Realised capital gain/loss for a fiscal year.

    For each SELL in the given FY, the cost basis is the weighted average buy
    price of all prior (or same-FY) buys for that stock, or under `fifo`, the
    cost of the oldest parcels still held when it sold.

    gain_loss = proceeds - cost of the units sold
    proceeds  = (units × price) - fees

    A positive gain_loss means profit; negative means a loss.
    """
    return await reports.capital_gains_report(session, current_user.id, fy, method)


@router.get("/dividends", response_model=DividendsReport)
async def get_dividends_report(
    fy: Optional[int] = Query(default=None, description="AU fiscal year filter (by ex_date); omit for all-time"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    For each Dividend belonging to a stock the user has ever transacted,
    compute units held on the ex_date and the resulting amount received.
    """
    return await reports.dividends_report(session, current_user.id, fy)
