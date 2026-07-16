from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Numeric
from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

if TYPE_CHECKING:
    # only for type checkers; avoids runtime import cycles
    from .stock_models import Stock


class Dividend(SQLModel, table=True):
    """
    A stock-level dividend event (ex-date + per-share amount).

    Deliberately NOT user-scoped: the same real-world dividend applies to
    every holder of the stock. Per-user "amount received" is a derived
    quantity (units held on ex_date x amount_per_share), computed on read in
    report_routes.py rather than stored here, matching how holdings/capital
    gains are already computed live from Transaction rows instead of cached.
    """
    __table_args__ = (
        UniqueConstraint("stock_id", "ex_date", name="unique_stock_ex_date"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    stock_id: int = Field(foreign_key="stock.id", index=True, description="FK to stock; no cascade")

    ex_date: date = Field(index=True, description="Ex-dividend date")
    pay_date: Optional[date] = Field(default=None, description="Payment date, if known")
    amount_per_share: Decimal = Field(sa_type=Numeric(18, 6), description="Cash dividend per share")
    source: str = Field(default="yfinance", description="Data source of this record")

    create_datetime: datetime = Field(default_factory=datetime.now)
    write_datetime: datetime = Field(default_factory=datetime.now)

    # relationships
    stock: Stock = Relationship(back_populates="dividends")
