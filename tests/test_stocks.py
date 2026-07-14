"""Integration tests for /api/stocks routes."""
import pytest


STOCK_PAYLOAD = {"symbol": "BHP", "market": "ASX", "name": "BHP Group Limited"}


async def _create_stock(client, payload=None):
    resp = await client.post("/api/stocks/", json=payload or STOCK_PAYLOAD)
    assert resp.status_code == 201
    return resp.json()


class TestCreateStock:
    async def test_creates_and_returns_stock(self, client):
        data = await _create_stock(client)
        assert data["symbol"] == "BHP"
        assert data["market"] == "ASX"
        assert data["name"] == "BHP Group Limited"
        assert data["is_active"] is True
        assert "id" in data

    async def test_uppercases_symbol_and_market(self, client):
        resp = await client.post("/api/stocks/", json={"symbol": "cba", "market": "asx", "name": "Commonwealth Bank"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["symbol"] == "CBA"
        assert data["market"] == "ASX"

    async def test_duplicate_returns_400(self, client):
        await _create_stock(client)
        resp = await client.post("/api/stocks/", json=STOCK_PAYLOAD)
        assert resp.status_code == 400


class TestListStocks:
    async def test_returns_paginated_response(self, client):
        await _create_stock(client)
        resp = await client.get("/api/stocks/")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] >= 1

    async def test_filter_by_market(self, client):
        await _create_stock(client)
        await client.post("/api/stocks/", json={"symbol": "AAPL", "market": "NASDAQ", "name": "Apple"})
        import json
        filters = json.dumps([{"field": "market", "op": "==", "value": "ASX"}])
        resp = await client.get("/api/stocks/", params={"filters": filters})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(s["market"] == "ASX" for s in items)


class TestGetStock:
    async def test_get_by_id(self, client):
        created = await _create_stock(client)
        resp = await client.get(f"/api/stocks/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    async def test_get_by_market_symbol(self, client):
        await _create_stock(client)
        resp = await client.get("/api/stocks/ASX:BHP")
        assert resp.status_code == 200
        assert resp.json()["symbol"] == "BHP"

    async def test_get_nonexistent_returns_404(self, client):
        resp = await client.get("/api/stocks/9999")
        assert resp.status_code == 404

    async def test_invalid_format_returns_400(self, client):
        resp = await client.get("/api/stocks/invalid-format")
        assert resp.status_code == 400


class TestUpdateStock:
    async def test_update_name(self, client):
        created = await _create_stock(client)
        resp = await client.put(f"/api/stocks/{created['id']}", json={"name": "BHP Billiton"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "BHP Billiton"

    async def test_deactivate_sets_archived_at(self, client):
        created = await _create_stock(client)
        resp = await client.put(f"/api/stocks/{created['id']}", json={"name": created["name"], "is_active": False})
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_active"] is False

    async def test_update_nonexistent_returns_404(self, client):
        resp = await client.put("/api/stocks/9999", json={"name": "X"})
        assert resp.status_code == 404


class TestDeleteStock:
    async def test_delete_returns_204(self, client):
        created = await _create_stock(client)
        resp = await client.delete(f"/api/stocks/{created['id']}")
        assert resp.status_code == 204

    async def test_deleted_stock_is_gone(self, client):
        created = await _create_stock(client)
        await client.delete(f"/api/stocks/{created['id']}")
        resp = await client.get(f"/api/stocks/{created['id']}")
        assert resp.status_code == 404

    async def test_delete_nonexistent_returns_404(self, client):
        resp = await client.delete("/api/stocks/9999")
        assert resp.status_code == 404
