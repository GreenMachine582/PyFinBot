from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class CostMethod(str, Enum):
    """How a holding or a sell is costed: AVERAGE, the weighted average buy
    price (the default), or FIFO, parcels matched first in, first out."""
    AVERAGE = "average"
    FIFO = "fifo"


class HoldingItem(BaseModel):
    stock_id: int
    market: str
    symbol: str
    name: str
    units_held: float
    avg_cost_basis: float  # per unit: the average over all buys, or (FIFO) over the parcels still held
    total_dividends_received: float = 0.0  # sum of dividends with ex_date <= as_of


class HoldingsReport(BaseModel):
    as_of: date
    method: CostMethod = CostMethod.AVERAGE
    holdings: list[HoldingItem]


class CapitalGainsItem(BaseModel):
    stock_id: int
    market: str
    symbol: str
    name: str
    units_sold: float
    avg_cost_basis: float   # per unit sold: the weighted avg buy price, or (FIFO) the parcels sold
    proceeds: float         # total sell value (units * price) - fees
    gain_loss: float        # proceeds - cost_basis_total


class CapitalGainsReport(BaseModel):
    fy: int
    method: CostMethod = CostMethod.AVERAGE
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
