"""
Reporting endpoints.

GET /api/reports/holdings          — Units held per stock as of a given date.
GET /api/reports/capital-gains     — Realised gain/loss for a fiscal year (avg cost basis).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..core.dependencies import get_current_user
from ..db.session import get_session
from ..models.transaction_models import Transaction, TypeEnum
from ..models.user_models import User
from ..schemas.report_schemas import CapitalGainsItem, CapitalGainsReport, HoldingItem, HoldingsReport

router = APIRouter(prefix="/reports", tags=["Reports"])


# ---------------------------------------------------------------------------
# Holdings
# ---------------------------------------------------------------------------

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
    snapshot = as_of or date.today()

    stmt = (
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .where(Transaction.transaction_date <= snapshot)
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
        return HoldingsReport(as_of=snapshot, holdings=[])

    # Fetch stock metadata
    from ..models.stock_models import Stock
    stock_rows = await session.exec(select(Stock).where(Stock.id.in_(list(stock_ids))))
    stock_map = {s.id: s for s in stock_rows.all()}

    holdings: list[HoldingItem] = []
    for sid in stock_ids:
        buy_txns = buys.get(sid, [])
        sell_txns = sells.get(sid, [])

        buy_units = sum(Decimal(str(t.units)) for t in buy_txns)
        sell_units = sum(Decimal(str(t.units)) for t in sell_txns)
        units_held = buy_units - sell_units

        if units_held <= 0:
            continue

        # Weighted average buy price
        total_buy_value = sum(Decimal(str(t.units)) * Decimal(str(t.price)) for t in buy_txns)
        avg_cost = (total_buy_value / buy_units) if buy_units else Decimal("0")

        stock = stock_map.get(sid)
        if not stock:
            continue

        holdings.append(HoldingItem(
            stock_id=sid,
            market=stock.market,
            symbol=stock.symbol,
            name=stock.name,
            units_held=float(units_held),
            avg_cost_basis=float(avg_cost.quantize(Decimal("0.000001"))),
        ))

    holdings.sort(key=lambda h: (h.market, h.symbol))
    return HoldingsReport(as_of=snapshot, holdings=holdings)


# ---------------------------------------------------------------------------
# Capital gains
# ---------------------------------------------------------------------------

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
    # Load all transactions up to end of the FY (30 Jun of fy+1)
    fy_end = date(fy + 1, 6, 30)

    stmt = (
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .where(Transaction.transaction_date <= fy_end)
        .order_by(Transaction.transaction_date, Transaction.id)
    )
    result = await session.exec(stmt)
    all_txns = result.all()

    # Separate sells that fall in the target FY
    fy_sells: dict[int, list[Transaction]] = {}
    all_buys_by_stock: dict[int, list[Transaction]] = {}

    for t in all_txns:
        if t.type == TypeEnum.BUY:
            all_buys_by_stock.setdefault(t.stock_id, []).append(t)
        elif t.type == TypeEnum.SELL and t.fy == fy:
            fy_sells.setdefault(t.stock_id, []).append(t)

    if not fy_sells:
        return CapitalGainsReport(fy=fy, total_gain_loss=0.0, items=[])

    # Fetch stock metadata
    from ..models.stock_models import Stock
    stock_ids = list(fy_sells.keys())
    stock_rows = await session.exec(select(Stock).where(Stock.id.in_(stock_ids)))
    stock_map = {s.id: s for s in stock_rows.all()}

    items: list[CapitalGainsItem] = []
    total = Decimal("0")

    for sid, sells in fy_sells.items():
        buys = all_buys_by_stock.get(sid, [])

        # Weighted avg cost basis from ALL buys up to FY end
        total_buy_units = sum(Decimal(str(b.units)) for b in buys)
        total_buy_value = sum(Decimal(str(b.units)) * Decimal(str(b.price)) for b in buys)
        avg_cost = (total_buy_value / total_buy_units) if total_buy_units else Decimal("0")

        units_sold = sum(Decimal(str(s.units)) for s in sells)
        # proceeds = gross sell value minus fees
        proceeds = sum(
            Decimal(str(s.units)) * Decimal(str(s.price)) - Decimal(str(s.fees))
            for s in sells
        )
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
        total_gain_loss=float(total.quantize(Decimal("0.000001"))),
        items=items,
    )
