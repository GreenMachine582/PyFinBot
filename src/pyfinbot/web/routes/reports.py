import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from greentechhub_core.identity import Identity
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core import reports
from ...core.fiscal_year import au_fiscal_year
from ...db.session import get_session
from ...models.transaction_models import Transaction
from ...schemas.report_schemas import CapitalGainsReport, DividendsReport, HoldingsReport
from ..deps import page_identity
from ..templating import templates

router = APIRouter(prefix="/reports", dependencies=[Depends(page_identity)])

TABS = [
    {"key": "holdings", "label": "Holdings", "icon": "briefcase", "url": "/reports/holdings"},
    {"key": "gains", "label": "Capital gains", "icon": "graph-up-arrow", "url": "/reports/gains"},
    {"key": "dividends", "label": "Dividend income", "icon": "cash-coin", "url": "/reports/dividends"},
]


def _parse_date(value: str | None) -> date:
    try:
        return date.fromisoformat(value) if value else date.today()
    except ValueError:
        return date.today()


def _parse_int(value: str | None) -> int | None:
    return int(value) if value and value.lstrip("-").isdigit() else None


async def _user_fys(session: AsyncSession, identity: Identity) -> list[int]:
    """The FYs the user has transactions in, newest first."""
    fys = (await session.exec(select(Transaction.fy).where(Transaction.user_id == identity.subject).distinct())).all()
    return sorted(fys, reverse=True)


async def _gains_fy(session: AsyncSession, identity: Identity, value: str | None) -> tuple[int, list[int]]:
    """The requested FY, else the user's latest (else the current one), plus
    the FY options for the picker."""
    fys = await _user_fys(session, identity)
    fy = _parse_int(value)
    if fy is None:
        fy = fys[0] if fys else au_fiscal_year(date.today())
    return fy, fys


@router.get("")
async def reports_page(request: Request, tab: str = "holdings"):
    active = tab if tab in {t["key"] for t in TABS} else "holdings"
    return templates.TemplateResponse(request, "reports.html", {"tabs": TABS, "active": active})


@router.get("/holdings")
async def holdings(request: Request, as_of: str | None = None,
                   identity: Identity = Depends(page_identity), session: AsyncSession = Depends(get_session)):
    report = await reports.holdings_report(session, identity.subject, _parse_date(as_of))
    return templates.TemplateResponse(request, "_report_holdings.html", {
        "report": report,
        "cost_base": sum(h.units_held * h.avg_cost_basis for h in report.holdings),
        "dividends": sum(h.total_dividends_received for h in report.holdings),
    })


@router.get("/gains")
async def gains(request: Request, fy: str | None = None,
                identity: Identity = Depends(page_identity), session: AsyncSession = Depends(get_session)):
    year, fys = await _gains_fy(session, identity, fy)
    report = await reports.capital_gains_report(session, identity.subject, year)
    return templates.TemplateResponse(request, "_report_gains.html", {
        "report": report, "fys": sorted(set(fys) | {year}, reverse=True),
    })


@router.get("/dividends")
async def dividends(request: Request, fy: str | None = None,
                    identity: Identity = Depends(page_identity), session: AsyncSession = Depends(get_session)):
    report = await reports.dividends_report(session, identity.subject, _parse_int(fy))
    return templates.TemplateResponse(request, "_report_dividends.html", {
        "report": report, "fys": await _user_fys(session, identity),
    })


def _holdings_rows(report: HoldingsReport):
    yield ["Market", "Symbol", "Name", "Units held", "Avg cost", "Cost base", "Dividends received"]
    for h in report.holdings:
        yield [h.market, h.symbol, h.name, h.units_held, h.avg_cost_basis,
               round(h.units_held * h.avg_cost_basis, 6), h.total_dividends_received]


def _gains_rows(report: CapitalGainsReport):
    yield ["Market", "Symbol", "Name", "Units sold", "Avg cost", "Proceeds", "Gain/loss"]
    for g in report.items:
        yield [g.market, g.symbol, g.name, g.units_sold, g.avg_cost_basis, g.proceeds, g.gain_loss]


def _dividends_rows(report: DividendsReport):
    yield ["Ex date", "Pay date", "Market", "Symbol", "Name", "Per share", "Units held", "Received"]
    for d in report.items:
        yield [d.ex_date, d.pay_date or "", d.market, d.symbol, d.name,
               d.amount_per_share, d.units_held_at_ex_date, d.amount_received]


@router.get("/{kind}.csv")
async def export_csv(kind: str, as_of: str | None = None, fy: str | None = None,
                     identity: Identity = Depends(page_identity), session: AsyncSession = Depends(get_session)):
    """The same report a pane shows, for the same filter, as a CSV download."""
    if kind == "holdings":
        snapshot = _parse_date(as_of)
        rows = _holdings_rows(await reports.holdings_report(session, identity.subject, snapshot))
        suffix = snapshot.isoformat()
    elif kind == "gains":
        year, _ = await _gains_fy(session, identity, fy)
        rows = _gains_rows(await reports.capital_gains_report(session, identity.subject, year))
        suffix = f"fy{year}"
    elif kind == "dividends":
        year_or_all = _parse_int(fy)
        rows = _dividends_rows(await reports.dividends_report(session, identity.subject, year_or_all))
        suffix = f"fy{year_or_all}" if year_or_all is not None else "all"
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown report")

    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return Response(buf.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="pyfinbot-{kind}-{suffix}.csv"',
    })
