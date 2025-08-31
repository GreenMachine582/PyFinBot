from datetime import datetime, date
from typing import Optional, Union

from pydantic import BaseModel, Field

from ..models.transaction_models import TypeEnum


class TransactionBase(BaseModel):
    user_id: Optional[str] = None
    stock_id: int | str
    transaction_date: Optional[date] = Field(default_factory=date.today)
    type: TypeEnum
    units: float
    price: float
    fees: Optional[float] = 0.0
    notes: Optional[str] = None


class TransactionCreate(TransactionBase):
    stock_id: Union[int, str]  # int or market:symbol key


class TransactionRead(TransactionBase):
    id: int

    total_value: float
    cost: float
    fy: int

    create_datetime: datetime
    write_datetime: datetime


class TransactionUpdate(BaseModel):
    notes: Optional[str] = None
