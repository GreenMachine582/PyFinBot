"""The three reports as table rows (a header, then one row per item): what
the web's CSV downloads and the CLI's CSV output both write, so the two
never disagree."""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ..schemas.report_schemas import CapitalGainsReport, DividendsReport, HoldingsReport


def holdings_rows(report: HoldingsReport) -> Iterator[list[Any]]:
    yield ["Market", "Symbol", "Name", "Units held", "Avg cost", "Cost base", "Dividends received"]
    for h in report.holdings:
        yield [h.market, h.symbol, h.name, h.units_held, h.avg_cost_basis,
               round(h.units_held * h.avg_cost_basis, 6), h.total_dividends_received]


def gains_rows(report: CapitalGainsReport) -> Iterator[list[Any]]:
    yield ["Market", "Symbol", "Name", "Units sold", "Avg cost", "Proceeds", "Gain/loss"]
    for g in report.items:
        yield [g.market, g.symbol, g.name, g.units_sold, g.avg_cost_basis, g.proceeds, g.gain_loss]


def dividends_rows(report: DividendsReport) -> Iterator[list[Any]]:
    yield ["Ex date", "Pay date", "Market", "Symbol", "Name", "Per share", "Units held", "Received"]
    for d in report.items:
        yield [d.ex_date, d.pay_date or "", d.market, d.symbol, d.name,
               d.amount_per_share, d.units_held_at_ex_date, d.amount_received]
