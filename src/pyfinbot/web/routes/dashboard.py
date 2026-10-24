from datetime import date, datetime
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from greentechhub_core.dates import fiscal_year
from greentechhub_core.identity import Identity
from greentechhub_fastapi.audit import get_audit_store
from greentechhub_fastapi.query import optional_datetime
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core import report_series, reports
from ...core.activity import ACTIVITY_KINDS, activity_page
from ...db.session import get_session
from ..deps import page_identity
from ..templating import templates

router = APIRouter()

#: How many holdings the dashboard lists, largest cost base first.
TOP_HOLDINGS = 5


async def _activity(request: Request, identity: Identity, before: datetime | None = None) -> dict[str, Any]:
    """The activity feed's context: the signed-in user's own audit entries,
    a page at a time; none (and no section) when audit isn't registered."""
    store = get_audit_store(request)
    if store is None:
        return {"activity": None}
    rows, cursor = await activity_page(store, identity.subject, before=before)
    next_url = f"/activity?{urlencode({'before': cursor.isoformat()})}" if cursor else None
    return {"activity": rows, "activity_next_url": next_url, "activity_kinds": ACTIVITY_KINDS}


@router.get("/")
async def dashboard(request: Request, identity: Identity = Depends(page_identity),
                    session: AsyncSession = Depends(get_session)):
    """Summary tiles for today and the current FY, from the same report
    functions as the Reports page, plus the largest holdings."""
    today = date.today()
    fy = fiscal_year(today)
    holdings = await reports.holdings_report(session, identity.subject, today)
    gains = await reports.capital_gains_report(session, identity.subject, fy)
    dividends = await reports.dividends_report(session, identity.subject, fy)
    by_cost = sorted(holdings.holdings, key=lambda h: h.units_held * h.avg_cost_basis, reverse=True)
    # The tiles' sparklines: the last 12 months of cost base and dividends.
    cost_series = await report_series.cost_base_by_month(session, identity.subject, today)
    all_dividends = await reports.dividends_report(session, identity.subject)
    dividend_series = report_series.dividends_by_month(
        all_dividends.items, report_series.months_ago(today, 11), today)
    return templates.TemplateResponse(request, "dashboard.html", {
        "identity": identity,
        "fy": fy,
        "holdings": holdings,
        "top_holdings": by_cost[:TOP_HOLDINGS],
        "cost_base": sum(h.units_held * h.avg_cost_basis for h in holdings.holdings),
        "gains": gains,
        "dividends": dividends,
        # Left out while all zero: a flat line says nothing a new user needs.
        "cost_series": cost_series if any(v for _, v in cost_series) else None,
        "dividend_series": dividend_series if any(v for _, v in dividend_series) else None,
        **await _activity(request, identity),
    })


@router.get("/activity")
async def activity(request: Request, before: str | None = None, identity: Identity = Depends(page_identity)):
    """The feed's next page, for its "Load older" button: the entries older
    than `before`. An unreadable cursor gives the first page."""
    return templates.TemplateResponse(request, "_activity_page.html",
                                      await _activity(request, identity, optional_datetime(before)))
