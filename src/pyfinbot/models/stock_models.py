from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint, select
from sqlmodel.ext.asyncio.session import AsyncSession

if TYPE_CHECKING:
    # only for type checkers; avoids runtime import cycles
    from .dividend_models import Dividend
    from .transaction_models import Transaction


#: The longest symbol or market (the columns' limit).
CODE_MAX = 20


class Stock(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("symbol", "market", name="unique_symbol_market"),
    )
    id: int | None = Field(default=None, primary_key=True)
    symbol: str = Field(index=True, max_length=CODE_MAX, description="Stock symbol")
    market: str = Field(index=True, max_length=CODE_MAX, description="Stock market")
    name: str = Field(index=True, description="Full name of the stock")

    create_datetime: datetime = Field(default_factory=lambda: datetime.now(UTC))
    write_datetime: datetime = Field(default_factory=lambda: datetime.now(UTC))

    is_active: bool = Field(default=True)
    archived_at: datetime | None = None

    # relationships
    transactions: list["Transaction"] = Relationship(back_populates="stock")
    dividends: list["Dividend"] = Relationship(back_populates="stock")

    def set_active(self, active: bool, now: datetime | None = None) -> bool:
        """Activate or archive this stock: the one archive rule for the web
        form, bulk archive, the API and market sync. archived_at is stamped
        when archiving (an existing stamp is kept) and cleared on
        reactivation, so it never lingers on an active stock. Returns
        whether is_active changed."""
        now = now or datetime.now(UTC)
        changed = self.is_active != active
        self.is_active = active
        self.archived_at = None if active else (self.archived_at or now)
        self.write_datetime = now
        return changed

    @classmethod
    async def search(
            cls, session: AsyncSession, *, market: str, symbol: str
    ) -> Optional["Stock"]:
        """Search for a stock by market and symbol."""
        stmt = select(cls).where((cls.market == market) & (cls.symbol == symbol))
        result = await session.exec(stmt)
        return result.one_or_none()