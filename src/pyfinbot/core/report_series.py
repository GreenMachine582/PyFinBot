"""Chart data for the dashboard and the Reports panes (greentechhub-ui's
server-rendered charts), built from core/reports.py's report functions so a
chart always agrees with the tables beside it. Each series is (label, value)
pairs, oldest first: the shape gth_sparkline / gth_bar_chart /
gth_line_chart take."""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional

from greentechhub_core.dates import fiscal_year_label
from sqlmodel.ext.asyncio.session import AsyncSession

from ..schemas.report_schemas import CostMethod
from . import reports

Series = list[tuple[str, Decimal]]


def _month_label(d: date) -> str:
    return d.strftime("%b %y")  # "Oct 25"


def _add_months(d: date, n: int) -> date:
    """The first of the month `n` months after (or before) `d`'s."""
    months = d.year * 12 + d.month - 1 + n
    return date(months // 12, months % 12 + 1, 1)


def months_ago(d: date, n: int) -> date:
    """The first of the month `n` months before `d`'s: months_ago(today, 11)
    starts a 12-month window ending this month."""
    return _add_months(d, -n)


def months_between(start: date, end: date) -> list[date]:
    """The first of each month from `start`'s to `end`'s, inclusive."""
    first, last = start.replace(day=1), end.replace(day=1)
    out = []
    while first <= last:
        out.append(first)
        first = _add_months(first, 1)
    return out


async def cost_base_by_month(session: AsyncSession, user_id: Optional[str], today: date,
                             months: int = 12) -> Series:
    """The cost base at average cost at each of the last `months` month-ends,
    the last point being `today` itself."""
    series: Series = []
    for first in months_between(months_ago(today, months - 1), today):
        as_of = min(_add_months(first, 1) - timedelta(days=1), today)
        report = await reports.holdings_report(session, user_id, as_of)
        cost = sum((Decimal(str(h.units_held)) * Decimal(str(h.avg_cost_basis)) for h in report.holdings),
                   Decimal(0))
        series.append((_month_label(first), cost))
    return series


def dividends_by_month(items: Iterable[Any], start: date, end: date) -> Series:
    """Dividend items' amount_received summed by ex-date month (the reports'
    convention), every month from `start` to `end`, empty months as 0."""
    totals = {m: Decimal(0) for m in months_between(start, end)}
    for item in items:
        month = item.ex_date.replace(day=1)
        if month in totals:
            totals[month] += Decimal(str(item.amount_received))
    return [(_month_label(m), v) for m, v in totals.items()]


async def gains_by_fy(session: AsyncSession, user_id: Optional[str], fys: Sequence[int],
                      method: CostMethod = CostMethod.AVERAGE) -> Series:
    """The net realised gain/loss of each FY in `fys`, oldest first."""
    series: Series = []
    for fy in sorted(fys):
        report = await reports.capital_gains_report(session, user_id, fy, method)
        series.append((fiscal_year_label(fy), Decimal(str(report.total_gain_loss))))
    return series
