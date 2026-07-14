"""Integration tests for /api/auth/login and JWT-protected route access."""

from .conftest import register_and_login


async def _register(client, user_id="user-123", password="hunter2!"):
    resp = await client.post("/api/users/", json={"id": user_id, "password": password})
    assert resp.status_code == 201
    return resp.json()


class TestLogin:
    async def test_login_success(self, client):
        await _register(client)
        resp = await client.post(
            "/api/auth/login", data={"username": "user-123", "password": "hunter2!"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["token_type"] == "bearer"
        assert data["access_token"]

    async def test_wrong_password_returns_401(self, client):
        await _register(client)
        resp = await client.post(
            "/api/auth/login", data={"username": "user-123", "password": "wrong"}
        )
        assert resp.status_code == 401

    async def test_unknown_user_returns_401(self, client):
        resp = await client.post(
            "/api/auth/login", data={"username": "no-such-user", "password": "hunter2!"}
        )
        assert resp.status_code == 401


class TestProtectedRouteAccess:
    async def test_no_token_returns_401(self, client):
        resp = await client.get("/api/users/user-123")
        assert resp.status_code == 401

    async def test_malformed_token_returns_401(self, client):
        resp = await client.get(
            "/api/users/user-123", headers={"Authorization": "Bearer not-a-real-token"}
        )
        assert resp.status_code == 401

    async def test_valid_token_grants_access(self, client):
        await _register(client)
        headers = await register_and_login(client, "user-456")
        resp = await client.get("/api/users/user-456", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == "user-456"
