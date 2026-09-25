"""Integration tests for the /dividends web page (yfinance mocked)."""
from datetime import date
from types import SimpleNamespace
from decimal import Decimal
from unittest.mock import patch

import pandas as pd

from pyfinbot.core.market_sync import sync_guard
from pyfinbot.web.routes.dividends import LOCK

from .conftest import create_stock, hx_triggers, web_login

HX = {"HX-Request": "true"}
FETCH = "pyfinbot.core.dividend_sync.yf.Ticker"
HISTORY = {date(2024, 3, 1): Decimal("0.72"), date(2024, 9, 5): Decimal("0.74")}


async def _buy(client, stock_id: int) -> None:
    resp = await client.post("/transactions", data={
        "stock_id": stock_id, "transaction_date": "2024-01-10", "type": "Buy",
        "units": "10", "price": "40", "fees": "0",
    })
    assert resp.status_code == 204, resp.text


def _fake_fetch(history=HISTORY):
    """Stub yfinance: every ticker returns `history` as its dividends series."""
    series = pd.Series({pd.Timestamp(d): float(a) for d, a in history.items()})
    return patch("pyfinbot.core.dividend_sync.yf.Ticker", return_value=SimpleNamespace(dividends=series))


class TestAuthGuard:
    async def test_page_redirects_to_login(self, client):
        resp = await client.get("/dividends", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/login"

    async def test_htmx_sync_gets_hx_redirect(self, client):
        resp = await client.post("/dividends/sync", headers=HX, follow_redirects=False)
        assert resp.status_code == 401
        assert resp.headers["HX-Redirect"] == "/login"


class TestPage:
    async def test_renders_sync_controls(self, client):
        await web_login(client, "web-divs")
        resp = await client.get("/dividends")
        assert resp.status_code == 200
        assert "Sync all my stocks" in resp.text
        assert "/stocks/options" in resp.text  # the one-stock picker
        assert 'href="/dividends" aria-current="page"' in resp.text


class TestSync:
    async def test_sync_all_my_stocks(self, client):
        await web_login(client, "web-divs")
        bhp = await create_stock(client)
        await create_stock(client, "CBA", name="Commonwealth Bank")  # never traded: out of scope
        await _buy(client, bhp["id"])
        with _fake_fetch():
            resp = await client.post("/dividends/sync", headers=HX)
        assert resp.status_code == 200
        assert "Dividend sync results — 1 stock" in resp.text
        assert "2 new" in resp.text and "0 failed" in resp.text
        triggers = hx_triggers(resp)
        assert triggers["showToast"]["kind"] == "success"
        assert triggers["showToast"]["message"] == "2 new, 0 updated."

        with _fake_fetch():
            resp = await client.post("/dividends/sync")
        assert hx_triggers(resp)["showToast"]["message"] == "Already up to date."

    async def test_sync_one_stock(self, client):
        await web_login(client, "web-divs")
        cba = await create_stock(client, "CBA", name="Commonwealth Bank")
        with _fake_fetch():
            resp = await client.post("/dividends/sync", data={"stock_id": str(cba["id"])})
        assert "Dividend sync results — ASX:CBA" in resp.text
        assert hx_triggers(resp)["showToast"]["title"] == "Dividend sync finished — ASX:CBA"

    async def test_unknown_stock_id(self, client):
        await web_login(client, "web-divs")
        resp = await client.post("/dividends/sync", data={"stock_id": "999999"})
        assert resp.status_code == 204
        assert hx_triggers(resp)["showToast"]["message"] == "Pick a stock from the list first."

    async def test_no_transactions(self, client):
        await web_login(client, "web-divs")
        resp = await client.post("/dividends/sync")
        assert resp.status_code == 204
        assert hx_triggers(resp)["showToast"]["kind"] == "info"

    async def test_fetch_failure_is_listed(self, client):
        await web_login(client, "web-divs")
        stock = await create_stock(client, "XYZ", market="NYSE", name="No mapping")
        await _buy(client, stock["id"])
        resp = await client.post("/dividends/sync")  # real fetcher: NYSE has no yfinance mapping
        assert "1 failed" in resp.text
        assert "NYSE:XYZ: No yfinance mapping for market: NYSE" in resp.text
        assert hx_triggers(resp)["showToast"]["kind"] == "danger"

    async def test_refused_while_running(self, client):
        await web_login(client, "web-divs")
        stock = await create_stock(client)
        await _buy(client, stock["id"])
        with sync_guard(LOCK) as held, patch(FETCH) as mock_fetch:
            assert held
            resp = await client.post("/dividends/sync")
        assert resp.status_code == 204
        assert hx_triggers(resp)["showToast"]["kind"] == "warning"
        mock_fetch.assert_not_called()
