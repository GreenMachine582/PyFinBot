from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from greentechhub_core.dates import fiscal_year, fiscal_year_bounds
from greentechhub_core.identity import Identity
from greentechhub_fastapi.downloads import csv_download
from greentechhub_fastapi.query import optional_choice, optional_date, optional_int
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core import report_rows, report_series, reports
from ...db.session import get_session
from ...models.transaction_models import Transaction
from ...schemas.report_schemas import CostMethod
from ..deps import page_identity
from ..templating import templates

router = APIRouter(prefix="/reports", dependencies=[Depends(page_identity)])

TABS = [
    {"key": "holdings", "label": "Holdings", "icon": "briefcase", "url": "/reports/holdings"},
    {"key": "gains", "label": "Capital gains", "icon": "graph-up-arrow", "url": "/reports/gains"},
    {"key": "dividends", "label": "Dividend income", "icon": "cash-coin", "url": "/reports/dividends"},
]

METHODS = [(CostMethod.AVERAGE.value, "Average"), (CostMethod.FIFO.value, "FIFO")]


async def _user_fys(session: AsyncSession, identity: Identity) -> list[int]:
    """The FYs the user has transactions in, newest first."""
    fys = (await session.exec(select(Transaction.fy).where(Transaction.user_id == identity.subject).distinct())).all()
    return sorted(fys, reverse=True)


async def _gains_fy(session: AsyncSession, identity: Identity, value: str | None) -> tuple[int, list[int]]:
    """The requested FY, else the user's latest (else the current one), plus
    the FY options for the picker."""
    fys = await _user_fys(session, identity)
    fy = optional_int(value)
    if fy is None:
        fy = fys[0] if fys else fiscal_year(date.today())
    return fy, fys


@router.get("")
async def reports_page(request: Request, tab: str = "holdings"):
    active = tab if tab in {t["key"] for t in TABS} else "holdings"
    return templates.TemplateResponse(request, "reports.html", {"tabs": TABS, "active": active})


@router.get("/holdings")
async def holdings(request: Request, as_of: str | None = None, method: str | None = None,
                   identity: Identity = Depends(page_identity), session: AsyncSession = Depends(get_session)):
    snapshot = optional_date(as_of, date.today())
    cost_method = optional_choice(method, CostMethod, CostMethod.AVERAGE)
    report = await reports.holdings_report(session, identity.subject, snapshot, cost_method)
    return templates.TemplateResponse(request, "_report_holdings.html", {
        "report": report, "methods": METHODS,
        "cost_base": sum(h.units_held * h.avg_cost_basis for h in report.holdings),
        "dividends": sum(h.total_dividends_received for h in report.holdings),
    })


@router.get("/gains")
async def gains(request: Request, fy: str | None = None, method: str | None = None,
                identity: Identity = Depends(page_identity), session: AsyncSession = Depends(get_session)):
    year, fys = await _gains_fy(session, identity, fy)
    cost_method = optional_choice(method, CostMethod, CostMethod.AVERAGE)
    report = await reports.capital_gains_report(session, identity.subject, year, cost_method)
    # Net gain/loss by FY for the bar chart: only worth drawing over 2+ years.
    by_fy = await report_series.gains_by_fy(session, identity.subject, fys, cost_method) if len(fys) > 1 else []
    return templates.TemplateResponse(request, "_report_gains.html", {
        "report": report, "fys": sorted(set(fys) | {year}, reverse=True), "methods": METHODS,
        "gains_by_fy": by_fy,
    })


@router.get("/dividends")
async def dividends(request: Request, fy: str | None = None,
                    identity: Identity = Depends(page_identity), session: AsyncSession = Depends(get_session)):
    report = await reports.dividends_report(session, identity.subject, optional_int(fy))
    # Received by month for the line chart: the FY's 12 months, or all time
    # from the first ex-date to the last.
    by_month: report_series.Series = []
    if report.items:
        if report.fy is not None:
            start, end = fiscal_year_bounds(report.fy)
        else:
            dates = [item.ex_date for item in report.items]
            start, end = min(dates), max(dates)
        by_month = report_series.dividends_by_month(report.items, start, end)
    return templates.TemplateResponse(request, "_report_dividends.html", {
        "report": report, "fys": await _user_fys(session, identity), "dividends_by_month": by_month,
    })


@router.get("/{kind}.csv")
async def export_csv(kind: str, as_of: str | None = None, fy: str | None = None, method: str | None = None,
                     identity: Identity = Depends(page_identity), session: AsyncSession = Depends(get_session)):
    """The same report a pane shows, for the same filter, as a CSV download."""
    cost_method = optional_choice(method, CostMethod, CostMethod.AVERAGE)
    # The method only goes in the filename when it isn't the default, so
    # average exports keep their old names.
    method_suffix = "" if cost_method == CostMethod.AVERAGE else f"-{cost_method.value}"
    if kind == "holdings":
        snapshot = optional_date(as_of, date.today())
        rows = report_rows.holdings_rows(await reports.holdings_report(session, identity.subject, snapshot, cost_method))
        suffix = snapshot.isoformat() + method_suffix
    elif kind == "gains":
        year, _ = await _gains_fy(session, identity, fy)
        rows = report_rows.gains_rows(await reports.capital_gains_report(session, identity.subject, year, cost_method))
        suffix = f"fy{year}{method_suffix}"
    elif kind == "dividends":
        year_or_all = optional_int(fy)
        rows = report_rows.dividends_rows(await reports.dividends_report(session, identity.subject, year_or_all))
        suffix = f"fy{year_or_all}" if year_or_all is not None else "all"
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown report")

    return csv_download(rows, f"pyfinbot-{kind}-{suffix}.csv")
