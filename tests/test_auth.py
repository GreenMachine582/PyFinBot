"""Integration tests for /api/auth/login and JWT-protected route access."""

from .conftest import create_user, register_and_login, user_id


async def _register(client, user_id="user-123", password="hunter2!"):
    await create_user(client, user_id, password)


class TestLogin:
    async def test_login_success(self, gth_client):
        await _register(gth_client)
        resp = await gth_client.post(
            "/api/auth/login", data={"username": "user-123", "password": "hunter2!"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["token_type"] == "bearer"
        assert data["access_token"]

    async def test_wrong_password_returns_401(self, gth_client):
        await _register(gth_client)
        resp = await gth_client.post(
            "/api/auth/login", data={"username": "user-123", "password": "wrong"}
        )
        assert resp.status_code == 401

    async def test_unknown_user_returns_401(self, gth_client):
        resp = await gth_client.post(
            "/api/auth/login", data={"username": "no-such-user", "password": "hunter2!"}
        )
        assert resp.status_code == 401


class TestProtectedRouteAccess:
    async def test_no_token_returns_401(self, gth_client):
        resp = await gth_client.get("/api/users/user-123")
        assert resp.status_code == 401

    async def test_malformed_token_returns_401(self, gth_client):
        resp = await gth_client.get(
            "/api/users/user-123", headers={"Authorization": "Bearer not-a-real-token"}
        )
        assert resp.status_code == 401

    async def test_valid_token_grants_access(self, gth_client):
        await _register(gth_client)
        headers = await register_and_login(gth_client, "user-456")
        me = await user_id("user-456")
        resp = await gth_client.get(f"/api/users/{me}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["username"] == "user-456"
