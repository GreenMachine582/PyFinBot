from typing import Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, Field, UniqueConstraint, select


class Stock(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("symbol", "market", name="unique_symbol_market"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    symbol: str = Field(index=True, max_length=20, description="Stock symbol")
    market: str = Field(index=True, max_length=20, description="Stock market")
    name: str = Field(index=True, description="Full name of the stock")

    create_datetime: datetime = Field(default_factory=datetime.now)
    write_datetime: datetime = Field(default_factory=datetime.now)

    is_active: bool = Field(default=True)
    archived_at: Optional[datetime] = None

    @classmethod
    async def search(
            cls, session: AsyncSession, *, market: str, symbol: str
    ) -> Optional["Stock"]:
        """Search for a stock by market and symbol."""
        stmt = select(cls).where((cls.market == market) & (cls.symbol == symbol))
        result = await session.execute(stmt)
        return result.scalar_one_or_none()