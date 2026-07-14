from __future__ import annotations

from datetime import datetime, date
from typing import Optional, Union

from pydantic import BaseModel, Field, ConfigDict, field_validator

from ..models.transaction_models import TypeEnum


class StockRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    market: str
    symbol: str
    name: Optional[str] = None


class TransactionBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: Optional[str] = None
    stock_id: int | str
    transaction_date: Optional[date] = Field(default_factory=date.today)
    type: TypeEnum
    units: float
    price: float
    fees: Optional[float] = 0.0
    notes: Optional[str] = None

    @field_validator("transaction_date", mode="before")
    @classmethod
    def parse_transaction_date(cls, v):
        if v is None or isinstance(v, date):
            return v
        if isinstance(v, str):
            # Try dd/MM/yyyy first
            if "/" in v:
                try:
                    return datetime.strptime(v, "%d/%m/%Y").date()
                except ValueError:
                    pass
            # Fallback to ISO (yyyy-MM-dd)
            try:
                return datetime.strptime(v, "%Y-%m-%d").date()
            except ValueError:
                raise ValueError(
                    f"Invalid date format: {v}. Expected dd/MM/yyyy or yyyy-MM-dd."
                )
        return v


class TransactionCreate(TransactionBase):
    stock_id: Union[int, str]  # int or market:symbol key


class TransactionRead(TransactionBase):
    id: int
    user_id: str

    stock: StockRef

    total_value: float
    cost: float
    fy: int

    create_datetime: datetime
    write_datetime: datetime


class TransactionUpdate(BaseModel):
    notes: Optional[str] = None
