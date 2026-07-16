"""Unit tests for dividend sync logic (mocked fetcher, no yfinance calls)."""
from datetime import date
from decimal import Decimal

from sqlmodel import select

from pyfinbot.core.dividend_sync import syncDividends
from pyfinbot.models.dividend_models import Dividend
from pyfinbot.models.stock_models import Stock


def _make_fetcher(data: dict):
    """Return a sync callable (symbol, market) -> {ex_date: amount_per_share}."""
    def fetcher(symbol, market):
        return data.get(symbol, {})
    return fetcher


async def _seed_stock(session, symbol="BHP", market="ASX", name="BHP Group") -> int:
    """Seed a Stock and return its id (a plain int, not the ORM object —
    syncDividends commits internally, which expires ORM objects from the
    same session; attribute access on an expired object triggers an
    implicit sync reload that breaks under asyncio)."""
    stock = Stock(symbol=symbol, market=market, name=name)
    session.add(stock)
    await session.commit()
    await session.refresh(stock)
    return stock.id


class TestSyncDividendsCreate:
    async def test_creates_new_dividends(self, session):
        stock_id = await _seed_stock(session)
        fetcher = _make_fetcher({
            "BHP": {date(2024, 8, 1): Decimal("1.10"), date(2025, 2, 1): Decimal("0.90")}
        })
        created, updated, errors = await syncDividends(session, stock_ids=[stock_id], fetch_for_symbol=fetcher)
        assert len(created) == 2
        assert updated == []
        assert errors == []

    async def test_dividends_exist_in_db_after_create(self, session):
        stock_id = await _seed_stock(session)
        fetcher = _make_fetcher({"BHP": {date(2024, 8, 1): Decimal("1.10")}})
        await syncDividends(session, stock_ids=[stock_id], fetch_for_symbol=fetcher)

        result = await session.exec(select(Dividend).where(Dividend.stock_id == stock_id))
        rows = result.all()
        assert len(rows) == 1
        assert rows[0].ex_date == date(2024, 8, 1)
        assert rows[0].amount_per_share == Decimal("1.10")
        assert rows[0].source == "yfinance"


class TestSyncDividendsUpdate:
    async def test_updates_changed_amount(self, session):
        stock_id = await _seed_stock(session)
        session.add(Dividend(stock_id=stock_id, ex_date=date(2024, 8, 1), amount_per_share=Decimal("1.00")))
        await session.commit()

        fetcher = _make_fetcher({"BHP": {date(2024, 8, 1): Decimal("1.25")}})
        created, updated, errors = await syncDividends(session, stock_ids=[stock_id], fetch_for_symbol=fetcher)
        assert created == []
        assert len(updated) == 1

        result = await session.exec(select(Dividend).where(Dividend.stock_id == stock_id))
        assert result.one().amount_per_share == Decimal("1.25")

    async def test_unchanged_amount_is_noop(self, session):
        stock_id = await _seed_stock(session)
        session.add(Dividend(stock_id=stock_id, ex_date=date(2024, 8, 1), amount_per_share=Decimal("1.00")))
        await session.commit()

        fetcher = _make_fetcher({"BHP": {date(2024, 8, 1): Decimal("1.00")}})
        created, updated, errors = await syncDividends(session, stock_ids=[stock_id], fetch_for_symbol=fetcher)
        assert created == []
        assert updated == []


class TestSyncDividendsIsolation:
    async def test_only_syncs_target_stock_ids(self, session):
        bhp_id = await _seed_stock(session, "BHP")
        await _seed_stock(session, "CBA", name="Commonwealth Bank")

        fetcher = _make_fetcher({
            "BHP": {date(2024, 8, 1): Decimal("1.10")},
            "CBA": {date(2024, 8, 1): Decimal("2.00")},
        })
        await syncDividends(session, stock_ids=[bhp_id], fetch_for_symbol=fetcher)

        result = await session.exec(select(Dividend))
        rows = result.all()
        assert len(rows) == 1
        assert rows[0].stock_id == bhp_id

    async def test_syncs_all_stocks_when_no_ids_given(self, session):
        await _seed_stock(session, "BHP")
        await _seed_stock(session, "CBA", name="Commonwealth Bank")

        fetcher = _make_fetcher({
            "BHP": {date(2024, 8, 1): Decimal("1.10")},
            "CBA": {date(2024, 8, 1): Decimal("2.00")},
        })
        created, updated, errors = await syncDividends(session, stock_ids=None, fetch_for_symbol=fetcher)
        assert len(created) == 2


class TestSyncDividendsErrors:
    async def test_fetch_error_is_captured_not_raised(self, session):
        stock_id = await _seed_stock(session)

        def broken_fetcher(symbol, market):
            raise ValueError("upstream failure")

        created, updated, errors = await syncDividends(session, stock_ids=[stock_id], fetch_for_symbol=broken_fetcher)
        assert created == []
        assert len(errors) == 1
        assert "upstream failure" in errors[0]
