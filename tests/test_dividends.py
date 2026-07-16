"""Integration tests for /api/dividends/sync (syncDividends mocked — no yfinance calls)."""
from unittest.mock import AsyncMock, patch

from .conftest import register_and_login

USER_ID = "div-user"


async def _create_stock(client, symbol="BHP", market="ASX", name="BHP Group"):
    resp = await client.post("/api/stocks/", json={"symbol": symbol, "market": market, "name": name})
    assert resp.status_code == 201
    return resp.json()


async def _buy(client, stock_id, headers, units=10, price=25, date="2024-08-01"):
    payload = {"stock_id": stock_id, "type": "Buy", "units": units, "price": price, "transaction_date": date}
    resp = await client.post("/api/transactions/", json=payload, headers=headers)
    assert resp.status_code == 201
    return resp.json()


class TestSyncDividendsEndpoint:
    async def test_no_token_returns_401(self, client):
        resp = await client.post("/api/dividends/sync")
        assert resp.status_code == 401

    async def test_syncs_stocks_from_users_transactions(self, client):
        headers = await register_and_login(client, USER_ID)
        stock = await _create_stock(client)
        await _buy(client, stock["id"], headers)

        with patch(
            "pyfinbot.api.dividend_routes.syncDividends",
            new=AsyncMock(return_value=(["ASX:BHP@2024-08-01"], [], [])),
        ) as mock_sync:
            resp = await client.post("/api/dividends/sync", headers=headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == ["ASX:BHP@2024-08-01"]
        assert data["updated"] == []
        assert data["errors"] == []

        _, kwargs = mock_sync.call_args
        assert kwargs["stock_ids"] == [stock["id"]]

    async def test_explicit_stock_id_bypasses_transaction_lookup(self, client):
        headers = await register_and_login(client, USER_ID)
        stock = await _create_stock(client)
        other_stock = await _create_stock(client, symbol="CBA", name="Commonwealth Bank")
        # user has never transacted `other_stock`, but ?stock_id= should sync it anyway
        await _buy(client, stock["id"], headers)

        with patch(
            "pyfinbot.api.dividend_routes.syncDividends",
            new=AsyncMock(return_value=([], [], [])),
        ) as mock_sync:
            resp = await client.post(
                "/api/dividends/sync", params={"stock_id": other_stock["id"]}, headers=headers
            )

        assert resp.status_code == 200
        _, kwargs = mock_sync.call_args
        assert kwargs["stock_ids"] == [other_stock["id"]]

    async def test_no_transactions_syncs_empty_list(self, client):
        headers = await register_and_login(client, USER_ID)

        with patch(
            "pyfinbot.api.dividend_routes.syncDividends",
            new=AsyncMock(return_value=([], [], [])),
        ) as mock_sync:
            resp = await client.post("/api/dividends/sync", headers=headers)

        assert resp.status_code == 200
        _, kwargs = mock_sync.call_args
        assert kwargs["stock_ids"] == []
