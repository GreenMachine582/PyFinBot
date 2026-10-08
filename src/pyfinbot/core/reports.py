"""
Report computations — shared by the /api/reports endpoints and the web
Reports page.

holdings_report       — Units held per stock as of a given date.
capital_gains_report  — Realised gain/loss for a fiscal year.
dividends_report      — Dividend income, optionally for one fiscal year.

Holdings and capital gains take a CostMethod: AVERAGE (the weighted average
buy price, the default) or FIFO (each sell takes the oldest parcels first).
Buy fees aren't part of the cost under either; sell fees reduce proceeds.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional

from greentechhub_core.dates import fiscal_year, fiscal_year_bounds
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..models.dividend_models import Dividend
from ..models.stock_models import Stock
from ..models.transaction_models import Transaction, TypeEnum
from ..schemas.report_schemas import (
    CapitalGainsItem,
    CapitalGainsReport,
    CostMethod,
    DividendItem,
    DividendsReport,
    HoldingItem,
    HoldingsReport,
)
from .holdings import units_held_as_of

ZERO = Decimal("0")


@dataclass
class _Parcel:
    units: Decimal
    price: Decimal


def _fifo(transactions: Iterable[Transaction]) -> tuple[list[_Parcel], list[tuple[Transaction, Decimal]]]:
    """Match one stock's sells to its buys first in, first out.

    Returns the parcels still held (oldest first) and each sell with the cost
    of the units it took. On one date buys count before sells. Units sold
    beyond those held match no parcel and cost nothing.
    """
    parcels: deque[_Parcel] = deque()
    costed: list[tuple[Transaction, Decimal]] = []
    for t in sorted(transactions, key=lambda t: (t.transaction_date, t.type != TypeEnum.BUY, t.id or 0)):
        units = Decimal(str(t.units))
        if t.type == TypeEnum.BUY:
            parcels.append(_Parcel(units, Decimal(str(t.price))))
            continue
        cost = ZERO
        while units > 0 and parcels:
            oldest = parcels[0]
            taken = min(units, oldest.units)
            cost += taken * oldest.price
            oldest.units -= taken
            units -= taken
            if oldest.units == 0:
                parcels.popleft()
        costed.append((t, cost))
    return list(parcels), costed


async def holdings_report(session: AsyncSession, user_id: Optional[str], as_of: date,
                          method: CostMethod = CostMethod.AVERAGE) -> HoldingsReport:
    """
    All stocks with a positive unit balance as of `as_of`.

    Units held = sum(BUY units) - sum(SELL units) for transactions up to and
    including `as_of`. The cost basis per unit is the weighted average buy
    price across all qualifying buys, or under FIFO, that of the parcels
    still held.
    """
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .where(Transaction.transaction_date <= as_of)
    )
    result = await session.exec(stmt)
    transactions = result.all()

    # Group by stock_id
    buys: dict[int, list[Transaction]] = {}
    sells: dict[int, list[Transaction]] = {}
    for t in transactions:
        bucket = buys if t.type == TypeEnum.BUY else sells
        bucket.setdefault(t.stock_id, []).append(t)

    stock_ids = set(buys) | set(sells)
    if not stock_ids:
        return HoldingsReport(as_of=as_of, method=method, holdings=[])

    # Fetch stock metadata
    stock_rows = await session.exec(select(Stock).where(col(Stock.id).in_(list(stock_ids))))
    stock_map = {s.id: s for s in stock_rows.all()}

    # Batch-load dividends (ex_date <= as_of) for all involved stocks, to
    # compute total_dividends_received per holding without a query per stock.
    div_rows = await session.exec(
        select(Dividend)
        .where(col(Dividend.stock_id).in_(list(stock_ids)))
        .where(Dividend.ex_date <= as_of)
    )
    dividends_by_stock: dict[int, list[Dividend]] = {}
    for d in div_rows.all():
        dividends_by_stock.setdefault(d.stock_id, []).append(d)

    holdings: list[HoldingItem] = []
    for sid in stock_ids:
        buy_txns = buys.get(sid, [])
        sell_txns = sells.get(sid, [])
        stock_txns = buy_txns + sell_txns

        buy_units = sum(Decimal(str(t.units)) for t in buy_txns)
        sell_units = sum(Decimal(str(t.units)) for t in sell_txns)
        units_held = buy_units - sell_units

        if units_held <= 0:
            continue

        if method == CostMethod.FIFO:
            held, _ = _fifo(stock_txns)
            held_units = sum((p.units for p in held), start=ZERO)
            held_value = sum((p.units * p.price for p in held), start=ZERO)
            avg_cost = (held_value / held_units) if held_units else ZERO
        else:
            # Weighted average buy price
            total_buy_value = sum(Decimal(str(t.units)) * Decimal(str(t.price)) for t in buy_txns)
            avg_cost = (total_buy_value / buy_units) if buy_units else Decimal("0")

        stock = stock_map.get(sid)
        if not stock:
            continue

        div_total = sum(
            (units_held_as_of(stock_txns, d.ex_date) * Decimal(str(d.amount_per_share))
             for d in dividends_by_stock.get(sid, [])),
            start=Decimal("0"),
        )

        holdings.append(HoldingItem(
            stock_id=sid,
            market=stock.market,
            symbol=stock.symbol,
            name=stock.name,
            units_held=float(units_held),
            avg_cost_basis=float(avg_cost.quantize(Decimal("0.000001"))),
            total_dividends_received=float(div_total.quantize(Decimal("0.000001"))),
        ))

    holdings.sort(key=lambda h: (h.market, h.symbol))
    return HoldingsReport(as_of=as_of, method=method, holdings=holdings)


async def capital_gains_report(session: AsyncSession, user_id: Optional[str], fy: int,
                               method: CostMethod = CostMethod.AVERAGE) -> CapitalGainsReport:
    """
    Realised capital gain/loss for a fiscal year.

    For each SELL in the given FY, the cost basis is the weighted average buy
    price of all prior (or same-FY) buys for that stock, or under FIFO, the
    cost of the oldest parcels still held when it sold.

    gain_loss = proceeds - cost of the units sold
    proceeds  = (units × price) - fees

    A positive gain_loss means profit; negative means a loss.
    """
    # Load all transactions up to end of the FY (30 Jun of fy+1)
    fy_end = fiscal_year_bounds(fy)[1]

    stmt = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .where(Transaction.transaction_date <= fy_end)
        .order_by(col(Transaction.transaction_date), col(Transaction.id))
    )
    result = await session.exec(stmt)
    all_txns = result.all()

    # Every stock's transactions, and the sells that fall in the target FY
    txns_by_stock: dict[int, list[Transaction]] = {}
    fy_sells: dict[int, list[Transaction]] = {}

    for t in all_txns:
        txns_by_stock.setdefault(t.stock_id, []).append(t)
        if t.type == TypeEnum.SELL and t.fy == fy:
            fy_sells.setdefault(t.stock_id, []).append(t)

    if not fy_sells:
        return CapitalGainsReport(fy=fy, method=method, total_gain_loss=0.0, items=[])

    # Fetch stock metadata
    stock_ids = list(fy_sells.keys())
    stock_rows = await session.exec(select(Stock).where(col(Stock.id).in_(stock_ids)))
    stock_map = {s.id: s for s in stock_rows.all()}

    items: list[CapitalGainsItem] = []
    total = Decimal("0")

    for sid, sells in fy_sells.items():
        units_sold = sum((Decimal(str(s.units)) for s in sells), start=ZERO)
        # proceeds = gross sell value minus fees
        proceeds = sum(
            (Decimal(str(s.units)) * Decimal(str(s.price)) - Decimal(str(s.fees)) for s in sells),
            start=ZERO,
        )
        if method == CostMethod.FIFO:
            _, costed = _fifo(txns_by_stock[sid])
            cost_basis_total = sum((cost for sell, cost in costed if sell.fy == fy), start=ZERO)
            avg_cost = (cost_basis_total / units_sold) if units_sold else ZERO
        else:
            # Weighted avg cost basis from ALL buys up to FY end
            buys = [t for t in txns_by_stock[sid] if t.type == TypeEnum.BUY]
            total_buy_units = sum((Decimal(str(b.units)) for b in buys), start=ZERO)
            total_buy_value = sum((Decimal(str(b.units)) * Decimal(str(b.price)) for b in buys), start=ZERO)
            avg_cost = (total_buy_value / total_buy_units) if total_buy_units else ZERO
            cost_basis_total = avg_cost * units_sold
        gain_loss = proceeds - cost_basis_total

        stock = stock_map.get(sid)
        if not stock:
            continue

        items.append(CapitalGainsItem(
            stock_id=sid,
            market=stock.market,
            symbol=stock.symbol,
            name=stock.name,
            units_sold=float(units_sold),
            avg_cost_basis=float(avg_cost.quantize(Decimal("0.000001"))),
            proceeds=float(proceeds.quantize(Decimal("0.000001"))),
            gain_loss=float(gain_loss.quantize(Decimal("0.000001"))),
        ))
        total += gain_loss

    items.sort(key=lambda i: (i.market, i.symbol))
    return CapitalGainsReport(
        fy=fy,
        method=method,
        total_gain_loss=float(total.quantize(Decimal("0.000001"))),
        items=items,
    )


async def dividends_report(session: AsyncSession, user_id: Optional[str],
                           fy: Optional[int] = None) -> DividendsReport:
    """
    For each Dividend belonging to a stock the user has ever transacted,
    compute units held on the ex_date and the resulting amount received.
    """
    txn_stmt = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(col(Transaction.transaction_date), col(Transaction.id))
    )
    txns = (await session.exec(txn_stmt)).all()

    txns_by_stock: dict[int, list[Transaction]] = {}
    for t in txns:
        txns_by_stock.setdefault(t.stock_id, []).append(t)

    if not txns_by_stock:
        return DividendsReport(fy=fy, total_dividends_received=0.0, items=[])

    div_stmt = select(Dividend).where(col(Dividend.stock_id).in_(list(txns_by_stock.keys())))
    dividends = (await session.exec(div_stmt)).all()

    stock_rows = await session.exec(select(Stock).where(col(Stock.id).in_(list(txns_by_stock.keys()))))
    stock_map = {s.id: s for s in stock_rows.all()}

    items: list[DividendItem] = []
    total = Decimal("0")
    for d in dividends:
        if fy is not None and fiscal_year(d.ex_date) != fy:
            continue
        units = units_held_as_of(txns_by_stock.get(d.stock_id, []), d.ex_date)
        if units <= 0:
            continue
        amount = (units * Decimal(str(d.amount_per_share))).quantize(Decimal("0.000001"))
        stock = stock_map.get(d.stock_id)
        if not stock:
            continue
        items.append(DividendItem(
            stock_id=d.stock_id,
            market=stock.market,
            symbol=stock.symbol,
            name=stock.name,
            ex_date=d.ex_date,
            pay_date=d.pay_date,
            amount_per_share=float(d.amount_per_share),
            units_held_at_ex_date=float(units),
            amount_received=float(amount),
        ))
        total += amount

    items.sort(key=lambda i: (i.ex_date, i.market, i.symbol))
    return DividendsReport(fy=fy, total_dividends_received=float(total), items=items)
