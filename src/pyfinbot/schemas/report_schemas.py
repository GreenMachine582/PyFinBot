from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel


class HoldingItem(BaseModel):
    stock_id: int
    market: str
    symbol: str
    name: str
    units_held: float
    avg_cost_basis: float  # average price paid per unit across all buys
    total_dividends_received: float = 0.0  # sum of dividends with ex_date <= as_of


class HoldingsReport(BaseModel):
    as_of: date
    holdings: list[HoldingItem]


class CapitalGainsItem(BaseModel):
    stock_id: int
    market: str
    symbol: str
    name: str
    units_sold: float
    avg_cost_basis: float   # weighted avg buy price at time of each sell
    proceeds: float         # total sell value (units * price) - fees
    gain_loss: float        # proceeds - cost_basis_total


class CapitalGainsReport(BaseModel):
    fy: int
    total_gain_loss: float
    items: list[CapitalGainsItem]


class DividendItem(BaseModel):
    stock_id: int
    market: str
    symbol: str
    name: str
    ex_date: date
    pay_date: Optional[date] = None
    amount_per_share: float
    units_held_at_ex_date: float
    amount_received: float


class DividendsReport(BaseModel):
    fy: Optional[int] = None
    total_dividends_received: float
    items: list[DividendItem]
