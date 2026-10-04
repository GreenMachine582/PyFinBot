"""Listing through greentechhub: the API list routes take fastapi's
PageParams and core's page() (where / order_by / paginate), and the web
tables core's order_by + paginate — replacing PyFinBot's web/paging.py,
core/sorting.py and core/sa_filters_compat.py. Bad sort or filters stay a
400 (api/query.py)."""
import importlib.util
import json

import pytest

from .conftest import create_stock, register_and_login, web_login

HX = {"HX-Request": "true"}


@pytest.mark.parametrize("module", ["pyfinbot.web.paging", "pyfinbot.core.sorting",
                                    "pyfinbot.core.sa_filters_compat"])
def test_hand_rolled_query_modules_are_gone(module):
    assert importlib.util.find_spec(module) is None


async def _stocks(client, **params):
    resp = await client.get("/api/stocks/", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _seed_stocks(client):
    for symbol, market in (("AAA", "ASX"), ("BBB", "ASX"), ("CCC", "NYSE")):
        await create_stock(client, symbol, market, f"{symbol} Ltd")


class TestApiStocks:
    async def test_default_sort_is_market_then_symbol(self, client):
        await _seed_stocks(client)
        items = (await _stocks(client))["items"]
        assert [(s["market"], s["symbol"]) for s in items] == [("ASX", "AAA"), ("ASX", "BBB"), ("NYSE", "CCC")]

    async def test_sort_descending(self, client):
        await _seed_stocks(client)
        assert [s["symbol"] for s in (await _stocks(client, sort="-symbol"))["items"]] == ["CCC", "BBB", "AAA"]

    async def test_or_group_and_ignored_unknown_field(self, client):
        await _seed_stocks(client)
        filters = json.dumps({"or": [{"field": "symbol", "op": "eq", "value": "AAA"},
                                     {"field": "market", "op": "==", "value": "NYSE"}]})
        assert {s["symbol"] for s in (await _stocks(client, filters=filters))["items"]} == {"AAA", "CCC"}
        unknown = json.dumps([{"field": "nope", "op": "eq", "value": "x"}])
        assert (await _stocks(client, filters=unknown))["total"] == 3

    async def test_flat_filter_string(self, client):
        await _seed_stocks(client)
        assert [s["symbol"] for s in (await _stocks(client, filter="symbol:contains:bb"))["items"]] == ["BBB"]

    async def test_paging(self, client):
        await _seed_stocks(client)
        body = await _stocks(client, page=2, size=1)
        assert [s["symbol"] for s in body["items"]] == ["BBB"]
        assert (body["total"], body["page"], body["size"], body["pages"]) == (3, 2, 1, 3)

    @pytest.mark.parametrize("filters", [
        json.dumps([{"field": "symbol", "op": "ilike", "value": "%A%"}]),  # an old sqlalchemy-filters op
        json.dumps({"not": {"field": "symbol", "op": "eq", "value": "AAA"}}),
        json.dumps([{"field": "symbol", "op": "eq"}]),
    ])
    async def test_unsupported_filters_are_400_invalid_filters(self, client, filters):
        resp = await client.get("/api/stocks/", params={"filters": filters})
        assert resp.status_code == 400
        assert resp.json()["code"] == "invalid_filters"

    async def test_bad_sort_is_400_invalid_sort(self, client):
        resp = await client.get("/api/stocks/", params={"sort": "symbol,-"})
        assert resp.status_code == 400
        assert resp.json()["code"] == "invalid_sort"


class TestApiTransactions:
    async def test_user_scoped_sorted_and_nested_stock(self, client):
        stock = await create_stock(client, "QRY", "ASX", "Query Ltd")
        mine = await register_and_login(client, "query-a")
        theirs = await register_and_login(client, "query-b")
        for day, headers in (("2024-08-01", mine), ("2024-09-01", mine), ("2024-10-01", theirs)):
            resp = await client.post("/api/transactions/", headers=headers, json={
                "stock_id": stock["id"], "type": "Buy", "units": 1, "price": 1, "fees": 0,
                "transaction_date": day})
            assert resp.status_code == 201, resp.text

        body = (await client.get("/api/transactions/", headers=mine)).json()
        assert [t["transaction_date"] for t in body["items"]] == ["2024-09-01", "2024-08-01"]  # newest first
        assert body["items"][0]["stock"] == {"market": "ASX", "symbol": "QRY", "name": "Query Ltd"}

        # Filtering on another user's id can only narrow the user's own rows.
        other = json.dumps([{"field": "user_id", "op": "eq", "value": "query-b"}])
        assert (await client.get("/api/transactions/", headers=mine, params={"filters": other})).json()["total"] == 0
        by_date = json.dumps([{"field": "date", "op": "gte", "value": "2024-08-15"}])
        resp = await client.get("/api/transactions/", headers=mine, params={"filters": by_date, "sort": "date"})
        assert [t["transaction_date"] for t in resp.json()["items"]] == ["2024-09-01"]


class TestWebTables:
    async def test_stock_table_sorts_and_pages_with_tie_breakers(self, client):
        await web_login(client, "query-web")
        for symbol in ("TIEB", "TIEA", "TIEC"):
            await create_stock(client, symbol, "ASX", "Same Name")  # the sort key ties on name
        resp = await client.get("/stocks", headers=HX, params={"q": "TIE", "sort": "name", "size": 10})
        page = resp.text
        assert page.index("TIEA") < page.index("TIEB") < page.index("TIEC")  # then market, symbol
        resp = await client.get("/stocks", headers=HX, params={"q": "TIE", "sort": "name", "dir": "desc",
                                                               "size": 10})
        page = resp.text
        assert page.index("TIEC") < page.index("TIEB") < page.index("TIEA")
