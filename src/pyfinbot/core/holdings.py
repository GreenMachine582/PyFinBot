"""Shared units-held-as-of-date math, extracted from report_routes.get_holdings
so it can be reused for dividend-total calculations without duplicating it."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable

from ..models.transaction_models import Transaction, TypeEnum


def units_held_as_of(transactions: Iterable[Transaction], as_of: date) -> Decimal:
    """Net units held (BUY - SELL) as of `as_of`, from an unfiltered iterable of
    a single stock's transactions (any date range, any order)."""
    transactions = list(transactions)
    buy_units = sum(
        (Decimal(str(t.units)) for t in transactions
         if t.type == TypeEnum.BUY and t.transaction_date <= as_of),
        start=Decimal("0"),
    )
    sell_units = sum(
        (Decimal(str(t.units)) for t in transactions
         if t.type == TypeEnum.SELL and t.transaction_date <= as_of),
        start=Decimal("0"),
    )
    return buy_units - sell_units
