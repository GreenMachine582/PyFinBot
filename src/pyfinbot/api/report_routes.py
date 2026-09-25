"""
Reporting endpoints. The computations live in core/reports.py (shared with
the web Reports page).

GET /api/reports/holdings          — Units held per stock as of a given date.
GET /api/reports/capital-gains     — Realised gain/loss for a fiscal year (avg cost basis).
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
from ..schemas.report_schemas import CapitalGainsReport, DividendsReport, HoldingsReport

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/holdings", response_model=HoldingsReport)
async def get_holdings(
    as_of: Optional[date] = Query(default=None, description="Snapshot date (default: today)"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Return all stocks with a positive unit balance as of `as_of` date.

    Units held = sum(BUY units) - sum(SELL units) for transactions up to and
    including `as_of`. Average cost basis is the weighted average buy price
    across all qualifying buy transactions.
    """
    return await reports.holdings_report(session, current_user.id, as_of or date.today())


@router.get("/capital-gains", response_model=CapitalGainsReport)
async def get_capital_gains(
    fy: int = Query(..., description="AU fiscal year (e.g. 2024 = FY ending 30 Jun 2025)"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Realised capital gain/loss for a fiscal year using average cost basis.

    For each SELL in the given FY, the cost basis is the weighted average buy
    price of all prior (or same-FY) buys for that stock.

    gain_loss = proceeds - (avg_cost_per_unit × units_sold)
    proceeds  = (units × price) - fees

    A positive gain_loss means profit; negative means a loss.
    """
    return await reports.capital_gains_report(session, current_user.id, fy)


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
