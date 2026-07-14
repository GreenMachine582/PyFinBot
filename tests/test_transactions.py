"""Integration tests for /api/transactions routes."""
import pytest

from .conftest import register_and_login

USER_ID = "user-abc"
OTHER_USER_ID = "user-other"


async def _create_stock(client, symbol="BHP", market="ASX", name="BHP Group"):
    resp = await client.post("/api/stocks/", json={"symbol": symbol, "market": market, "name": name})
    assert resp.status_code == 201
    return resp.json()


async def _create_transaction(client, stock_id, headers, **overrides):
    payload = {
        "stock_id": stock_id,
        "type": "Buy",
        "units": 10,
        "price": 25.5,
        "fees": 9.95,
        "transaction_date": "2024-08-01",
        **overrides,
    }
    resp = await client.post("/api/transactions/", json=payload, headers=headers)
    assert resp.status_code == 201
    return resp.json()


class TestCreateTransaction:
    async def test_creates_with_stock_id_int(self, client):
        headers = await register_and_login(client, USER_ID)
        stock = await _create_stock(client)
        data = await _create_transaction(client, stock["id"], headers)
        assert data["units"] == 10
        assert data["price"] == 25.5
        assert data["total_value"] == 255.0
        assert data["cost"] == pytest.approx(-264.95)
        assert data["fy"] == 2024
        assert data["stock"]["symbol"] == "BHP"

    async def test_creates_with_market_symbol_string(self, client):
        headers = await register_and_login(client, USER_ID)
        await _create_stock(client)
        data = await _create_transaction(client, "ASX:BHP", headers)
        assert data["stock"]["market"] == "ASX"
        assert data["stock"]["symbol"] == "BHP"

    async def test_user_id_comes_from_token(self, client):
        headers = await register_and_login(client, USER_ID)
        stock = await _create_stock(client)
        data = await _create_transaction(client, stock["id"], headers)
        assert data["user_id"] == USER_ID

    async def test_user_id_in_body_is_ignored(self, client):
        headers = await register_and_login(client, USER_ID)
        stock = await _create_stock(client)
        payload = {"stock_id": stock["id"], "type": "Buy", "units": 5, "price": 10,
                   "user_id": "body-user"}
        resp = await client.post("/api/transactions/", json=payload, headers=headers)
        assert resp.status_code == 201
        # user_id is no longer part of the request schema; the token's user wins.
        assert resp.json()["user_id"] == USER_ID

    async def test_no_token_returns_401(self, client):
        stock = await _create_stock(client)
        payload = {"stock_id": stock["id"], "type": "Buy", "units": 5, "price": 10}
        resp = await client.post("/api/transactions/", json=payload)
        assert resp.status_code == 401

    async def test_nonexistent_stock_returns_404(self, client):
        headers = await register_and_login(client, USER_ID)
        payload = {"stock_id": 9999, "type": "Buy", "units": 5, "price": 10}
        resp = await client.post("/api/transactions/", json=payload, headers=headers)
        assert resp.status_code == 404

    async def test_sell_cost_is_positive(self, client):
        headers = await register_and_login(client, USER_ID)
        stock = await _create_stock(client)
        data = await _create_transaction(
            client, stock["id"], headers, type="Sell", units=10, price=30, fees=9.95
        )
        assert data["cost"] == pytest.approx(290.05)


class TestListTransactions:
    async def test_no_token_returns_401(self, client):
        resp = await client.get("/api/transactions/")
        assert resp.status_code == 401

    async def test_returns_only_requesting_users_transactions(self, client):
        headers = await register_and_login(client, USER_ID)
        other_headers = await register_and_login(client, OTHER_USER_ID)
        stock = await _create_stock(client)
        await _create_transaction(client, stock["id"], headers)
        # Create for other user
        payload = {"stock_id": stock["id"], "type": "Buy", "units": 1, "price": 1}
        await client.post("/api/transactions/", json=payload, headers=other_headers)

        resp = await client.get("/api/transactions/", headers=headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(t["user_id"] == USER_ID for t in items)

    async def test_paginated_response_shape(self, client):
        headers = await register_and_login(client, USER_ID)
        stock = await _create_stock(client)
        await _create_transaction(client, stock["id"], headers)
        resp = await client.get("/api/transactions/", headers=headers)
        data = resp.json()
        assert "items" in data
        assert "total" in data


class TestGetTransaction:
    async def test_get_returns_transaction_with_stock(self, client):
        headers = await register_and_login(client, USER_ID)
        stock = await _create_stock(client)
        created = await _create_transaction(client, stock["id"], headers)
        resp = await client.get(f"/api/transactions/{created['id']}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == created["id"]
        assert data["stock"]["symbol"] == "BHP"

    async def test_other_user_gets_403(self, client):
        headers = await register_and_login(client, USER_ID)
        other_headers = await register_and_login(client, OTHER_USER_ID)
        stock = await _create_stock(client)
        created = await _create_transaction(client, stock["id"], headers)
        resp = await client.get(f"/api/transactions/{created['id']}", headers=other_headers)
        assert resp.status_code == 403

    async def test_nonexistent_returns_404(self, client):
        headers = await register_and_login(client, USER_ID)
        resp = await client.get("/api/transactions/9999", headers=headers)
        assert resp.status_code == 404


class TestUpdateTransaction:
    async def test_update_notes(self, client):
        headers = await register_and_login(client, USER_ID)
        stock = await _create_stock(client)
        created = await _create_transaction(client, stock["id"], headers)
        resp = await client.put(f"/api/transactions/{created['id']}",
                                json={"notes": "updated note"}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["notes"] == "updated note"

    async def test_other_user_gets_403(self, client):
        headers = await register_and_login(client, USER_ID)
        other_headers = await register_and_login(client, OTHER_USER_ID)
        stock = await _create_stock(client)
        created = await _create_transaction(client, stock["id"], headers)
        resp = await client.put(f"/api/transactions/{created['id']}",
                                json={"notes": "hack"}, headers=other_headers)
        assert resp.status_code == 403


class TestDeleteTransaction:
    async def test_delete_returns_204(self, client):
        headers = await register_and_login(client, USER_ID)
        stock = await _create_stock(client)
        created = await _create_transaction(client, stock["id"], headers)
        resp = await client.delete(f"/api/transactions/{created['id']}", headers=headers)
        assert resp.status_code == 204

    async def test_other_user_gets_403(self, client):
        headers = await register_and_login(client, USER_ID)
        other_headers = await register_and_login(client, OTHER_USER_ID)
        stock = await _create_stock(client)
        created = await _create_transaction(client, stock["id"], headers)
        resp = await client.delete(f"/api/transactions/{created['id']}", headers=other_headers)
        assert resp.status_code == 403

    async def test_delete_nonexistent_returns_404(self, client):
        headers = await register_and_login(client, USER_ID)
        resp = await client.delete("/api/transactions/9999", headers=headers)
        assert resp.status_code == 404
