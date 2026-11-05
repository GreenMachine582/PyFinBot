from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models.transaction_models import NOTES_MAX, TypeEnum


def parse_transaction_date(v):
    """Accepts a date/None as-is, otherwise parses dd/MM/yyyy or yyyy-MM-dd strings."""
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


class StockRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    market: str
    symbol: str
    name: str | None = None


class TransactionBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stock_id: int | str
    transaction_date: date | None = Field(default_factory=date.today)
    type: TypeEnum
    units: float
    price: float
    fees: float | None = 0.0
    notes: str | None = None

    _parse_transaction_date = field_validator("transaction_date", mode="before")(parse_transaction_date)


class TransactionCreate(TransactionBase):
    stock_id: int | str  # int or market:symbol key
    # Limited on the way in only, so TransactionRead still reads older, longer notes.
    notes: str | None = Field(default=None, max_length=NOTES_MAX)


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
    """Partial update — only fields actually sent are applied (exclude_unset)."""
    stock_id: int | str | None = None  # int or market:symbol key
    transaction_date: date | None = None
    type: TypeEnum | None = None
    units: float | None = None
    price: float | None = None
    fees: float | None = None
    notes: str | None = Field(default=None, max_length=NOTES_MAX)

    _parse_transaction_date = field_validator("transaction_date", mode="before")(parse_transaction_date)
