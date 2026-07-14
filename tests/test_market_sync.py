"""Unit tests for market sync logic (mocked fetcher, no HTTP calls)."""
import pytest
from sqlmodel import select

from pyfinbot.core.market_sync import syncMarket
from pyfinbot.models.stock_models import Stock


def _make_fetcher(data: dict):
    """Return a sync callable that returns the given symbol→name mapping."""
    def fetcher():
        return data
    return fetcher


class TestSyncMarketCreate:
    async def test_creates_new_stocks(self, session):
        fetcher = _make_fetcher({"BHP": "BHP Group", "CBA": "Commonwealth Bank"})
        created, updated, archived = await syncMarket(session, "ASX", fetch_data=fetcher)
        assert set(created) == {"BHP", "CBA"}
        assert updated == []
        assert archived == []

    async def test_stocks_exist_in_db_after_create(self, session):
        fetcher = _make_fetcher({"BHP": "BHP Group"})
        await syncMarket(session, "ASX", fetch_data=fetcher)
        result = await session.exec(select(Stock).where(Stock.symbol == "BHP"))
        stock = result.one_or_none()
        assert stock is not None
        assert stock.market == "ASX"
        assert stock.name == "BHP Group"
        assert stock.is_active is True


class TestSyncMarketUpdate:
    async def test_updates_changed_name(self, session):
        # Seed stock with old name
        session.add(Stock(symbol="BHP", market="ASX", name="Old Name"))
        await session.commit()

        fetcher = _make_fetcher({"BHP": "New Name"})
        created, updated, archived = await syncMarket(session, "ASX", fetch_data=fetcher)
        assert "BHP" in updated
        assert created == []

        result = await session.exec(select(Stock).where(Stock.symbol == "BHP"))
        assert result.one().name == "New Name"

    async def test_reactivates_archived_stock(self, session):
        from datetime import datetime
        session.add(Stock(symbol="BHP", market="ASX", name="BHP Group",
                          is_active=False, archived_at=datetime.now()))
        await session.commit()

        fetcher = _make_fetcher({"BHP": "BHP Group"})
        created, updated, archived = await syncMarket(session, "ASX", fetch_data=fetcher)
        assert "BHP" in updated

        result = await session.exec(select(Stock).where(Stock.symbol == "BHP"))
        stock = result.one()
        assert stock.is_active is True
        assert stock.archived_at is None


class TestSyncMarketArchive:
    async def test_archives_delisted_stocks(self, session):
        session.add(Stock(symbol="BHP", market="ASX", name="BHP Group"))
        session.add(Stock(symbol="DEL", market="ASX", name="Delisted Co"))
        await session.commit()

        fetcher = _make_fetcher({"BHP": "BHP Group"})  # DEL not in new list
        created, updated, archived = await syncMarket(session, "ASX", fetch_data=fetcher)
        assert "DEL" in archived

        result = await session.exec(select(Stock).where(Stock.symbol == "DEL"))
        stock = result.one()
        assert stock.is_active is False
        assert stock.archived_at is not None

    async def test_already_archived_not_double_archived(self, session):
        from datetime import datetime
        ts = datetime.now()
        session.add(Stock(symbol="DEL", market="ASX", name="Delisted",
                          is_active=False, archived_at=ts))
        await session.commit()

        fetcher = _make_fetcher({})
        created, updated, archived = await syncMarket(session, "ASX", fetch_data=fetcher)
        assert "DEL" not in archived  # already inactive, not re-archived


class TestSyncMarketIsolation:
    async def test_only_affects_target_market(self, session):
        session.add(Stock(symbol="AAPL", market="NASDAQ", name="Apple"))
        await session.commit()

        fetcher = _make_fetcher({"BHP": "BHP Group"})
        created, updated, archived = await syncMarket(session, "ASX", fetch_data=fetcher)

        result = await session.exec(select(Stock).where(Stock.symbol == "AAPL"))
        apple = result.one_or_none()
        assert apple is not None and apple.is_active is True  # untouched
