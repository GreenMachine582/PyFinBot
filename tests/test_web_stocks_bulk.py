"""Bulk archive / unarchive on the Stocks table (gth_data_table's bulk bar
posts the checked rows as repeated `ids`), and Stock.set_active — the one
archive rule the web form, the bulk routes, the API and market sync share."""
from datetime import datetime, timezone

from sqlmodel import select

from pyfinbot.models.stock_models import Stock

from .conftest import create_stock, hx_triggers, web_login

HX = {"HX-Request": "true"}
T1 = datetime(2025, 1, 1, tzinfo=timezone.utc)
T2 = datetime(2025, 2, 1, tzinfo=timezone.utc)


async def _stock(session, stock_id: int) -> Stock:
    return (await session.exec(
        select(Stock).where(Stock.id == stock_id).execution_options(populate_existing=True))).one()


class TestSetActive:
    def test_archive_stamps_and_reports_the_change(self):
        stock = Stock(symbol="A", market="ASX", name="A")
        assert stock.set_active(False, T1) is True
        assert (stock.is_active, stock.archived_at, stock.write_datetime) == (False, T1, T1)

    def test_archiving_again_keeps_the_first_stamp(self):
        stock = Stock(symbol="A", market="ASX", name="A", is_active=False, archived_at=T1)
        assert stock.set_active(False, T2) is False
        assert stock.archived_at == T1 and stock.write_datetime == T2

    def test_reactivating_clears_the_stamp(self):
        stock = Stock(symbol="A", market="ASX", name="A", is_active=False, archived_at=T1)
        assert stock.set_active(True, T2) is True
        assert stock.is_active and stock.archived_at is None


class TestTable:
    async def test_renders_the_bulk_bar_and_a_select_cell_per_row(self, client):
        await web_login(client, "bulk-view")
        await create_stock(client, "BLKA", "ASX", "Bulk A")
        page = (await client.get("/stocks", headers=HX, params={"q": "BLK"})).text
        assert 'hx-post="/stocks/bulk-archive"' in page and 'hx-post="/stocks/bulk-unarchive"' in page
        assert page.count("data-gth-select ") == 1
        assert 'aria-label="Select ASX:BLKA"' in page


class TestBulkRoutes:
    async def test_needs_login(self, client):
        resp = await client.post("/stocks/bulk-archive", headers=HX, data={"ids": ["1"]}, follow_redirects=False)
        assert resp.status_code == 401
        assert resp.headers["HX-Redirect"] == "/login"

    async def test_archive_two_then_unarchive_one(self, client, session):
        await web_login(client, "bulk-user")
        a = await create_stock(client, "BLKA", "ASX", "Bulk A")
        b = await create_stock(client, "BLKB", "ASX", "Bulk B")

        resp = await client.post("/stocks/bulk-archive", headers=HX, data={"ids": [str(a["id"]), str(b["id"])]})
        assert resp.status_code == 204
        toast = hx_triggers(resp)
        assert toast["showToast"]["message"] == "Archived 2 stocks"
        assert toast["showToast"]["title"] == "Stocks archived"
        assert "stocksChanged" in toast
        for stock_id in (a["id"], b["id"]):
            stock = await _stock(session, stock_id)
            assert not stock.is_active and stock.archived_at is not None

        resp = await client.post("/stocks/bulk-unarchive", headers=HX, data={"ids": [str(a["id"])]})
        assert hx_triggers(resp)["showToast"]["message"] == "Unarchived 1 stock"
        stock = await _stock(session, a["id"])
        assert stock.is_active and stock.archived_at is None
        assert not (await _stock(session, b["id"])).is_active

    async def test_already_archived_junk_and_unknown_ids_are_not_counted(self, client, session):
        await web_login(client, "bulk-mixed")
        done = await create_stock(client, "BLKD", "ASX", "Bulk Done")
        todo = await create_stock(client, "BLKT", "ASX", "Bulk Todo")
        await client.post("/stocks/bulk-archive", headers=HX, data={"ids": [str(done["id"])]})
        first_stamp = (await _stock(session, done["id"])).archived_at

        resp = await client.post("/stocks/bulk-archive", headers=HX, data={
            "ids": [str(done["id"]), str(todo["id"]), "nope", "999999"]})
        assert hx_triggers(resp)["showToast"]["message"] == "Archived 1 stock"
        assert (await _stock(session, done["id"])).archived_at == first_stamp

    async def test_nothing_to_do_is_an_info_toast(self, client):
        await web_login(client, "bulk-empty")
        resp = await client.post("/stocks/bulk-unarchive", headers=HX, data={})
        toast = hx_triggers(resp)
        assert toast["showToast"]["kind"] == "info"
        assert toast["showToast"]["message"] == "No stocks to unarchive."
        assert "stocksChanged" in toast


async def test_api_reactivation_clears_archived_at(client, session):
    stock = await create_stock(client, "BLKR", "ASX", "Bulk Reactivate")
    await client.put(f"/api/stocks/{stock['id']}", json={"is_active": False})
    assert (await _stock(session, stock["id"])).archived_at is not None
    resp = await client.put(f"/api/stocks/{stock['id']}", json={"is_active": True, "name": "Renamed"})
    assert resp.status_code == 200 and resp.json()["name"] == "Renamed"
    after = await _stock(session, stock["id"])
    assert after.is_active and after.archived_at is None
