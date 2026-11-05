

from pydantic import BaseModel, Field

from ..models.stock_models import CODE_MAX


class StockBase(BaseModel):
    market: str = Field(max_length=CODE_MAX)
    symbol: str = Field(max_length=CODE_MAX)
    name: str
    is_active: bool = True


class StockCreate(StockBase):
    pass


class StockRead(StockBase):
    id: int


class StockUpdate(BaseModel):
    name: str | None = None
    is_active: bool = True


class SyncResult(BaseModel):
    created: list[str]
    updated: list[str]
    archived: list[str]
