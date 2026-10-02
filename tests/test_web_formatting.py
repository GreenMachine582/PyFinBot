"""The shared greentechhub-ui money / number / date filters, as rendered on
the transactions table and the report panes (gth-ui v0.11.0 adoption)."""
import greentechhub_ui

from pyfinbot.web.templating import templates

from .conftest import create_stock, web_login
from .test_reports import _seed_dividend
from .test_web_reports import HX, _txn


def test_filters_are_gth_uis_not_app_overrides():
    filters = templates.env.filters
    # gth-ui registers its own filters (context-aware wrappers since v0.12, so
    # they can follow the user's settings); nothing of ours shadows them.
    for name in ("money", "number", "date"):
        assert filters[name] is greentechhub_ui.formatting.FILTERS[name]
    assert "qty" not in filters
    assert filters["fy"](2024) == "2024–25"  # still PyFinBot's own


class TestTransactionsTable:
    async def test_dates_numbers_and_money(self, client):
        await web_login(client, "web-formatting")
        bhp = await create_stock(client)
        await _txn(client, bhp["id"], "Buy", "100", "40.50", "2024-07-10", fees="9.95")
        resp = await client.get("/transactions", headers=HX)
        row = resp.text.split("<tbody")[1]
        assert "10 Jul 2024" in row
        assert ">100<" in row and ">40.5<" in row  # units / price: full precision, zeros trimmed
        assert ">$9.95<" in row  # fees
        assert ">$4,050.00<" in row  # total value
        assert ">-$4,059.95<" in row  # a buy's cost: sign before the symbol


class TestReports:
    async def test_holdings_units_from_floats_and_money(self, client):
        await web_login(client, "web-formatting")
        bhp = await create_stock(client)
        await _txn(client, bhp["id"], "Buy", "100", "40", "2024-07-10")
        await _txn(client, bhp["id"], "Buy", "50", "55", "2024-08-10")
        resp = await client.get("/reports/holdings", headers=HX, params={"as_of": "2025-06-30"})
        assert ">150<" in resp.text and "150.0" not in resp.text  # float units, no noise
        assert "$45.00" in resp.text  # average cost basis
        assert "$6,750.00" in resp.text  # cost base

    async def test_dividend_dates(self, client, session):
        await web_login(client, "web-formatting")
        bhp = await create_stock(client)
        await _txn(client, bhp["id"], "Buy", "200", "40", "2024-07-10")
        await _seed_dividend(session, bhp["id"], "2024-09-01", "1.50")
        resp = await client.get("/reports/dividends", headers=HX)
        assert "1 Sep 2024" in resp.text
        assert ">—<" in resp.text  # no pay date: |date gives "", so the "or" fallback shows
        assert ">1.5<" in resp.text  # per share: |number, not rounded money
        assert "$300.00" in resp.text
