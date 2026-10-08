from datetime import date

from fastapi import APIRouter, Depends, Request
from greentechhub_core.dates import fiscal_year
from greentechhub_core.identity import Identity
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core import reports
from ...db.session import get_session
from ..deps import page_identity
from ..templating import templates

router = APIRouter()

#: How many holdings the dashboard lists, largest cost base first.
TOP_HOLDINGS = 5


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
    return templates.TemplateResponse(request, "dashboard.html", {
        "identity": identity,
        "fy": fy,
        "holdings": holdings,
        "top_holdings": by_cost[:TOP_HOLDINGS],
        "cost_base": sum(h.units_held * h.avg_cost_basis for h in holdings.holdings),
        "gains": gains,
        "dividends": dividends,
    })
