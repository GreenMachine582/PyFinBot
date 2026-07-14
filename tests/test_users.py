"""Integration tests for /api/users routes."""
import pytest


async def _create_user(client, user_id="user-123"):
    resp = await client.post("/api/users/", json={"id": user_id})
    assert resp.status_code == 201
    return resp.json()


class TestCreateUser:
    async def test_creates_and_returns_user(self, client):
        data = await _create_user(client)
        assert data["id"] == "user-123"
        assert data["active"] is True
        assert "create_datetime" in data

    async def test_duplicate_returns_400(self, client):
        await _create_user(client)
        resp = await client.post("/api/users/", json={"id": "user-123"})
        assert resp.status_code == 400


class TestListUsers:
    async def test_returns_list(self, client):
        await _create_user(client, "u1")
        await _create_user(client, "u2")
        resp = await client.get("/api/users/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2


class TestGetUser:
    async def test_get_by_id(self, client):
        await _create_user(client)
        resp = await client.get("/api/users/user-123")
        assert resp.status_code == 200
        assert resp.json()["id"] == "user-123"

    async def test_nonexistent_returns_404(self, client):
        resp = await client.get("/api/users/does-not-exist")
        assert resp.status_code == 404


class TestUpdateUser:
    async def test_deactivate_user(self, client):
        await _create_user(client)
        resp = await client.put("/api/users/user-123", json={"active": False})
        assert resp.status_code == 200
        assert resp.json()["active"] is False

    async def test_update_nonexistent_returns_404(self, client):
        resp = await client.put("/api/users/ghost", json={"active": False})
        assert resp.status_code == 404


class TestDeleteUser:
    async def test_delete_returns_204(self, client):
        await _create_user(client)
        resp = await client.delete("/api/users/user-123")
        assert resp.status_code == 204

    async def test_deleted_user_is_gone(self, client):
        await _create_user(client)
        await client.delete("/api/users/user-123")
        resp = await client.get("/api/users/user-123")
        assert resp.status_code == 404

    async def test_delete_nonexistent_returns_404(self, client):
        resp = await client.delete("/api/users/ghost")
        assert resp.status_code == 404
