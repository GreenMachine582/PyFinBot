from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Numeric
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    # only for type checkers; avoids runtime import cycles
    from .stock_models import Stock
    from .user_models import User


class TypeEnum(str, Enum):
    BUY = "Buy"
    SELL = "Sell"

    @classmethod
    def _missing_(cls, value):  # enables case-insensitive input
        if isinstance(value, str):
            for member in cls:
                if member.value.lower() == value.lower():
                    return member
        raise ValueError(f"Invalid transaction type: {value}")


class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.id", ondelete="CASCADE", index=True,
                         description="FK to user; cascades on delete")
    stock_id: int = Field(foreign_key="stock.id", description="FK to stock; no cascade")

    transaction_date: date = Field(default_factory=date.today, description="Transaction date")
    type: TypeEnum = Field(description="Transaction type")

    units: Decimal = Field(sa_type=Numeric(18, 6), description="Transaction units")
    price: Decimal = Field(sa_type=Numeric(18, 6), description="Price per unit")
    total_value: Decimal = Field(default=Decimal("0"), sa_type=Numeric(18, 6), description="units * price")
    fees: Decimal = Field(default=Decimal("0"), sa_type=Numeric(18, 6), description="Brokerage/fees")
    cost: Decimal = Field(default=Decimal("0"), sa_type=Numeric(18, 6),
                          description="Net cash movement (+sell -fees | -buy +fees)")
    notes: Optional[str] = Field(default=None, description="Transaction notes")

    # FY (AU: FY ends Jun 30 → July = new FY)
    fy: int = Field(default=0, description="Fiscal year")

    # Timestamps (UTC)
    create_datetime: datetime = Field(default_factory=datetime.now)
    write_datetime: datetime = Field(default_factory=datetime.now)

    # relationships
    stock: Stock = Relationship(back_populates="transactions")
    user: User = Relationship(back_populates="transactions")

    def model_post_init(self, __context):
        """Compute derived fields after (de)serialization."""
        if self.transaction_date is None:
            self.transaction_date = date.today()
        elif isinstance(self.transaction_date, datetime):
            self.transaction_date = self.transaction_date.date()

        # Ensure Decimal coercion
        self.units = Decimal(self.units)
        self.price = Decimal(self.price)
        self.fees = Decimal(self.fees)

        # Compute total_value
        self.total_value = (self.units * self.price).quantize(Decimal("0.000001"))

        # Compute cost: BUY is cash outflow (negative), SELL is inflow (positive)
        if self.type == TypeEnum.BUY:
            self.cost = (-self.total_value - self.fees).quantize(Decimal("0.000001"))
        else:
            self.cost = (self.total_value - self.fees).quantize(Decimal("0.000001"))

        # Compute fiscal year (AU: FY ends June 30)
        td: date = self.transaction_date
        self.fy = td.year - 1 if td.month <= 6 else td.year
