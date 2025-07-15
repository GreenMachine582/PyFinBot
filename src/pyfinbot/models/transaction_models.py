
from datetime import datetime, date
from enum import Enum
from typing import Optional

from sqlalchemy import Column, Integer, ForeignKey
from sqlmodel import SQLModel, Field


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
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE")),
        description="FK to user; cascades on delete"
    )
    stock_id: int = Field(
        sa_column=Column(Integer, ForeignKey("stock.id")),
        description="FK to stock; no cascade"
    )

    transaction_date: date = Field(default_factory=date.today, description="Transaction date")
    type: TypeEnum = Field(description="Transaction type")
    units: float = Field(description="Transaction units", decimal_places=2)
    price: float = Field(description="Transaction price", decimal_places=3)
    total_value: float = Field(default=0.0, description="Transaction total value", decimal_places=6)
    fees: float = Field(default=0.0, description="Transaction fees", decimal_places=2)
    cost: float = Field(default=0.0, description="Transaction cost", decimal_places=6)
    notes: Optional[str] = Field(default=None, description="Transaction notes")
    fy: int = Field(default=0, description="Fiscal year")

    create_datetime: datetime = Field(default_factory=datetime.now)
    write_datetime: datetime = Field(default_factory=datetime.now)

    def model_post_init(self, __context):
        """Compute remaining fields after initialisation."""
        if callable(self.transaction_date):
            self.transaction_date = self.transaction_date()

        # Compute total_value
        self.total_value = round(self.units * self.price, 6)

        # Compute cost
        if self.type == TypeEnum.BUY:
            self.cost = round(-self.total_value + self.fees)
        else:
            self.cost = round(self.total_value - self.fees, 6)

        # Fiscal year
        self.fy = self.transaction_date.year-1 if self.transaction_date.month <= 6 else self.transaction_date.year
