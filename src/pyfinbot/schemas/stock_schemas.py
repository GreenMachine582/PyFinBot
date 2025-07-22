
from typing import List, Optional

from pydantic import BaseModel


class StockBase(BaseModel):
    market: str
    symbol: str
    name: str
    is_active: bool = True


class StockCreate(StockBase):
    pass


class StockRead(StockBase):
    id: int


class StockUpdate(BaseModel):
    name: Optional[str] = None
    is_active: bool = True


class SyncResult(BaseModel):
    created: List[str]
    updated: List[str]
    archived: List[str]
