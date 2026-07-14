"""Integration tests for /api/transactions routes."""
import pytest


USER_ID = "user-abc"
HEADERS = {"X-User-ID": USER_ID}
OTHER_USER_HEADERS = {"X-User-ID": "user-other"}


async def _create_stock(client, symbol="BHP", market="ASX", name="BHP Group"):
    resp = await client.post("/api/stocks/", json={"symbol": symbol, "market": market, "name": name})
    assert resp.status_code == 201
    return resp.json()


async def _create_transaction(client, stock_id, **overrides):
    payload = {
        "stock_id": stock_id,
        "type": "Buy",
        "units": 10,
        "price": 25.5,
        "fees": 9.95,
        "transaction_date": "2024-08-01",
        **overrides,
    }
    resp = await client.post("/api/transactions/", json=payload, headers=HEADERS)
    assert resp.status_code == 201
    return resp.json()


class TestCreateTransaction:
    async def test_creates_with_stock_id_int(self, client):
        stock = await _create_stock(client)
        data = await _create_transaction(client, stock["id"])
        assert data["units"] == 10
        assert data["price"] == 25.5
        assert data["total_value"] == 255.0
        assert data["cost"] == pytest.approx(-264.95)
        assert data["fy"] == 2024
        assert data["stock"]["symbol"] == "BHP"

    async def test_creates_with_market_symbol_string(self, client):
        await _create_stock(client)
        data = await _create_transaction(client, "ASX:BHP")
        assert data["stock"]["market"] == "ASX"
        assert data["stock"]["symbol"] == "BHP"

    async def test_user_id_from_header(self, client):
        stock = await _create_stock(client)
        data = await _create_transaction(client, stock["id"])
        assert data["user_id"] == USER_ID

    async def test_user_id_from_body_overrides_header(self, client):
        stock = await _create_stock(client)
        payload = {"stock_id": stock["id"], "type": "Buy", "units": 5, "price": 10,
                   "user_id": "body-user"}
        resp = await client.post("/api/transactions/", json=payload, headers=HEADERS)
        assert resp.status_code == 201
        assert resp.json()["user_id"] == "body-user"

    async def test_no_user_id_returns_400(self, client):
        stock = await _create_stock(client)
        payload = {"stock_id": stock["id"], "type": "Buy", "units": 5, "price": 10}
        resp = await client.post("/api/transactions/", json=payload)
        assert resp.status_code == 400

    async def test_nonexistent_stock_returns_404(self, client):
        payload = {"stock_id": 9999, "type": "Buy", "units": 5, "price": 10}
        resp = await client.post("/api/transactions/", json=payload, headers=HEADERS)
        assert resp.status_code == 404

    async def test_sell_cost_is_positive(self, client):
        stock = await _create_stock(client)
        data = await _create_transaction(client, stock["id"], type="Sell", units=10, price=30, fees=9.95)
        assert data["cost"] == pytest.approx(290.05)


class TestListTransactions:
    async def test_requires_user_id_header(self, client):
        resp = await client.get("/api/transactions/")
        assert resp.status_code == 400

    async def test_returns_only_requesting_users_transactions(self, client):
        stock = await _create_stock(client)
        await _create_transaction(client, stock["id"])
        # Create for other user
        payload = {"stock_id": stock["id"], "type": "Buy", "units": 1, "price": 1}
        await client.post("/api/transactions/", json=payload, headers=OTHER_USER_HEADERS)

        resp = await client.get("/api/transactions/", headers=HEADERS)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(t["user_id"] == USER_ID for t in items)

    async def test_paginated_response_shape(self, client):
        stock = await _create_stock(client)
        await _create_transaction(client, stock["id"])
        resp = await client.get("/api/transactions/", headers=HEADERS)
        data = resp.json()
        assert "items" in data
        assert "total" in data


class TestGetTransaction:
    async def test_get_returns_transaction_with_stock(self, client):
        stock = await _create_stock(client)
        created = await _create_transaction(client, stock["id"])
        resp = await client.get(f"/api/transactions/{created['id']}", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == created["id"]
        assert data["stock"]["symbol"] == "BHP"

    async def test_other_user_gets_403(self, client):
        stock = await _create_stock(client)
        created = await _create_transaction(client, stock["id"])
        resp = await client.get(f"/api/transactions/{created['id']}", headers=OTHER_USER_HEADERS)
        assert resp.status_code == 403

    async def test_nonexistent_returns_404(self, client):
        resp = await client.get("/api/transactions/9999", headers=HEADERS)
        assert resp.status_code == 404


class TestUpdateTransaction:
    async def test_update_notes(self, client):
        stock = await _create_stock(client)
        created = await _create_transaction(client, stock["id"])
        resp = await client.put(f"/api/transactions/{created['id']}",
                                json={"notes": "updated note"}, headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["notes"] == "updated note"

    async def test_other_user_gets_403(self, client):
        stock = await _create_stock(client)
        created = await _create_transaction(client, stock["id"])
        resp = await client.put(f"/api/transactions/{created['id']}",
                                json={"notes": "hack"}, headers=OTHER_USER_HEADERS)
        assert resp.status_code == 403


class TestDeleteTransaction:
    async def test_delete_returns_204(self, client):
        stock = await _create_stock(client)
        created = await _create_transaction(client, stock["id"])
        resp = await client.delete(f"/api/transactions/{created['id']}", headers=HEADERS)
        assert resp.status_code == 204

    async def test_other_user_gets_403(self, client):
        stock = await _create_stock(client)
        created = await _create_transaction(client, stock["id"])
        resp = await client.delete(f"/api/transactions/{created['id']}", headers=OTHER_USER_HEADERS)
        assert resp.status_code == 403

    async def test_delete_nonexistent_returns_404(self, client):
        resp = await client.delete("/api/transactions/9999", headers=HEADERS)
        assert resp.status_code == 404
