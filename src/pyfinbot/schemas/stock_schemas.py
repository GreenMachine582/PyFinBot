
from typing import Optional

from pydantic import BaseModel

class StockBase(BaseModel):
    market: str
    symbol: str
    name: str


class StockCreate(StockBase):
    pass


class StockRead(StockBase):
    id: int


class StockUpdate(BaseModel):
    name: Optional[str] = None
