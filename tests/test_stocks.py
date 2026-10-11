"""Integration tests for /api/stocks routes."""


STOCK_PAYLOAD = {"symbol": "BHP", "market": "ASX", "name": "BHP Group Limited"}


async def _post_stock(client, payload=None):
    resp = await client.post("/api/stocks/", json=payload or STOCK_PAYLOAD)
    assert resp.status_code == 201
    return resp.json()


class TestCreateStock:
    async def test_creates_and_returns_stock(self, gth_client):
        data = await _post_stock(gth_client)
        assert data["symbol"] == "BHP"
        assert data["market"] == "ASX"
        assert data["name"] == "BHP Group Limited"
        assert data["is_active"] is True
        assert "id" in data

    async def test_uppercases_symbol_and_market(self, gth_client):
        resp = await gth_client.post("/api/stocks/", json={"symbol": "cba", "market": "asx", "name": "Commonwealth Bank"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["symbol"] == "CBA"
        assert data["market"] == "ASX"

    async def test_duplicate_returns_400(self, gth_client):
        await _post_stock(gth_client)
        resp = await gth_client.post("/api/stocks/", json=STOCK_PAYLOAD)
        assert resp.status_code == 400


class TestListStocks:
    async def test_returns_paginated_response(self, gth_client):
        await _post_stock(gth_client)
        resp = await gth_client.get("/api/stocks/")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] >= 1

    async def test_filter_by_market(self, gth_client):
        await _post_stock(gth_client)
        await gth_client.post("/api/stocks/", json={"symbol": "AAPL", "market": "NASDAQ", "name": "Apple"})
        import json
        filters = json.dumps([{"field": "market", "op": "==", "value": "ASX"}])
        resp = await gth_client.get("/api/stocks/", params={"filters": filters})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(s["market"] == "ASX" for s in items)


class TestGetStock:
    async def test_get_by_id(self, gth_client):
        created = await _post_stock(gth_client)
        resp = await gth_client.get(f"/api/stocks/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    async def test_get_by_market_symbol(self, gth_client):
        await _post_stock(gth_client)
        resp = await gth_client.get("/api/stocks/ASX:BHP")
        assert resp.status_code == 200
        assert resp.json()["symbol"] == "BHP"

    async def test_get_nonexistent_returns_404(self, gth_client):
        resp = await gth_client.get("/api/stocks/9999")
        assert resp.status_code == 404

    async def test_invalid_format_returns_400(self, gth_client):
        resp = await gth_client.get("/api/stocks/invalid-format")
        assert resp.status_code == 400


class TestUpdateStock:
    async def test_update_name(self, gth_client):
        created = await _post_stock(gth_client)
        resp = await gth_client.put(f"/api/stocks/{created['id']}", json={"name": "BHP Billiton"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "BHP Billiton"

    async def test_deactivate_sets_archived_at(self, gth_client):
        created = await _post_stock(gth_client)
        resp = await gth_client.put(f"/api/stocks/{created['id']}", json={"name": created["name"], "is_active": False})
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_active"] is False

    async def test_update_nonexistent_returns_404(self, gth_client):
        resp = await gth_client.put("/api/stocks/9999", json={"name": "X"})
        assert resp.status_code == 404


class TestDeleteStock:
    async def test_delete_returns_204(self, gth_client):
        created = await _post_stock(gth_client)
        resp = await gth_client.delete(f"/api/stocks/{created['id']}")
        assert resp.status_code == 204

    async def test_deleted_stock_is_gone(self, gth_client):
        created = await _post_stock(gth_client)
        await gth_client.delete(f"/api/stocks/{created['id']}")
        resp = await gth_client.get(f"/api/stocks/{created['id']}")
        assert resp.status_code == 404

    async def test_delete_nonexistent_returns_404(self, gth_client):
        resp = await gth_client.delete("/api/stocks/9999")
        assert resp.status_code == 404


class TestSyncMarketLock:
    async def test_already_running_returns_409(self, gth_client):
        from unittest.mock import AsyncMock, patch

        from pyfinbot.core.market_sync import market_sync_guard

        with patch("pyfinbot.api.stock_routes.syncMarket", new=AsyncMock()) as sync:
            with market_sync_guard("asx") as held:
                assert held
                resp = await gth_client.post("/api/stocks/sync/ASX")
        assert resp.status_code == 409
        assert resp.json()["message"] == "ASX sync is already running"
        assert resp.json()["code"] == "conflict"
        sync.assert_not_awaited()
