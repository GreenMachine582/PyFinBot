"""Unit tests for market sync logic (mocked fetcher, no HTTP calls)."""
from sqlmodel import select

from pyfinbot.core.market_sync import syncMarket
from pyfinbot.models.stock_models import Stock


def _make_fetcher(data: dict):
    """Return a sync callable that returns the given symbol→name mapping."""
    def fetcher():
        return data
    return fetcher


class TestSyncMarketCreate:
    async def test_creates_new_stocks(self, gth_session):
        fetcher = _make_fetcher({"BHP": "BHP Group", "CBA": "Commonwealth Bank"})
        created, updated, archived = await syncMarket(gth_session, "ASX", fetch_data=fetcher)
        assert set(created) == {"BHP", "CBA"}
        assert updated == []
        assert archived == []

    async def test_stocks_exist_in_db_after_create(self, gth_session):
        fetcher = _make_fetcher({"BHP": "BHP Group"})
        await syncMarket(gth_session, "ASX", fetch_data=fetcher)
        result = await gth_session.exec(select(Stock).where(Stock.symbol == "BHP"))
        stock = result.one_or_none()
        assert stock is not None
        assert stock.market == "ASX"
        assert stock.name == "BHP Group"
        assert stock.is_active is True


class TestSyncMarketUpdate:
    async def test_updates_changed_name(self, gth_session):
        # Seed stock with old name
        gth_session.add(Stock(symbol="BHP", market="ASX", name="Old Name"))
        await gth_session.commit()

        fetcher = _make_fetcher({"BHP": "New Name"})
        created, updated, archived = await syncMarket(gth_session, "ASX", fetch_data=fetcher)
        assert "BHP" in updated
        assert created == []

        result = await gth_session.exec(select(Stock).where(Stock.symbol == "BHP"))
        assert result.one().name == "New Name"

    async def test_reactivates_archived_stock(self, gth_session):
        from datetime import datetime, timezone
        gth_session.add(Stock(symbol="BHP", market="ASX", name="BHP Group",
                          is_active=False, archived_at=datetime.now(timezone.utc)))
        await gth_session.commit()

        fetcher = _make_fetcher({"BHP": "BHP Group"})
        created, updated, archived = await syncMarket(gth_session, "ASX", fetch_data=fetcher)
        assert "BHP" in updated

        result = await gth_session.exec(select(Stock).where(Stock.symbol == "BHP"))
        stock = result.one()
        assert stock.is_active is True
        assert stock.archived_at is None


class TestSyncMarketArchive:
    async def test_archives_delisted_stocks(self, gth_session):
        gth_session.add(Stock(symbol="BHP", market="ASX", name="BHP Group"))
        gth_session.add(Stock(symbol="DEL", market="ASX", name="Delisted Co"))
        await gth_session.commit()

        fetcher = _make_fetcher({"BHP": "BHP Group"})  # DEL not in new list
        created, updated, archived = await syncMarket(gth_session, "ASX", fetch_data=fetcher)
        assert "DEL" in archived

        result = await gth_session.exec(select(Stock).where(Stock.symbol == "DEL"))
        stock = result.one()
        assert stock.is_active is False
        assert stock.archived_at is not None

    async def test_already_archived_not_double_archived(self, gth_session):
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc)
        gth_session.add(Stock(symbol="DEL", market="ASX", name="Delisted",
                          is_active=False, archived_at=ts))
        await gth_session.commit()

        fetcher = _make_fetcher({})
        created, updated, archived = await syncMarket(gth_session, "ASX", fetch_data=fetcher)
        assert "DEL" not in archived  # already inactive, not re-archived


class TestSyncMarketIsolation:
    async def test_only_affects_target_market(self, gth_session):
        gth_session.add(Stock(symbol="AAPL", market="NASDAQ", name="Apple"))
        await gth_session.commit()

        fetcher = _make_fetcher({"BHP": "BHP Group"})
        created, updated, archived = await syncMarket(gth_session, "ASX", fetch_data=fetcher)

        result = await gth_session.exec(select(Stock).where(Stock.symbol == "AAPL"))
        apple = result.one_or_none()
        assert apple is not None and apple.is_active is True  # untouched
