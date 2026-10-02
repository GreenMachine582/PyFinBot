"""Integration tests for /api/users routes. Creating and listing users need
users.manage (the admin role); get/update/delete are self-only."""

from .conftest import create_user, make_admin, register_and_login


async def _admin_headers(client, user_id="admin-1"):
    headers = await register_and_login(client, user_id)
    await make_admin(client, user_id)
    return headers


async def _create_user(client, user_id="user-123", password="hunter2!"):
    await create_user(client, user_id, password)


class TestCreateUser:
    async def test_admin_creates_and_returns_user(self, client):
        headers = await _admin_headers(client)
        resp = await client.post("/api/users/", json={"id": "user-123", "password": "hunter2!"},
                                 headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "user-123"
        assert data["active"] is True
        assert "create_datetime" in data
        assert "password" not in data
        assert "password_hash" not in data
        login = await client.post("/api/auth/login", data={"username": "user-123", "password": "hunter2!"})
        assert login.status_code == 200

    async def test_duplicate_returns_400(self, client):
        headers = await _admin_headers(client)
        await _create_user(client)
        resp = await client.post("/api/users/", json={"id": "user-123", "password": "hunter2!"},
                                 headers=headers)
        assert resp.status_code == 400

    async def test_missing_password_returns_422(self, client):
        headers = await _admin_headers(client)
        resp = await client.post("/api/users/", json={"id": "user-123"}, headers=headers)
        assert resp.status_code == 422

    async def test_no_open_registration(self, client):
        resp = await client.post("/api/users/", json={"id": "user-123", "password": "hunter2!"})
        assert resp.status_code == 401

    async def test_non_admin_gets_403(self, client):
        headers = await register_and_login(client, "plain-user")
        resp = await client.post("/api/users/", json={"id": "user-123", "password": "hunter2!"},
                                 headers=headers)
        assert resp.status_code == 403


class TestListUsers:
    async def test_admin_gets_every_user(self, client):
        await _create_user(client, "u1")
        await _create_user(client, "u2")
        headers = await _admin_headers(client, "u3")
        resp = await client.get("/api/users/", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert {"u1", "u2", "u3"} <= {u["id"] for u in data}

    async def test_non_admin_gets_403(self, client):
        headers = await register_and_login(client, "plain-user")
        resp = await client.get("/api/users/", headers=headers)
        assert resp.status_code == 403

    async def test_no_token_returns_401(self, client):
        resp = await client.get("/api/users/")
        assert resp.status_code == 401


class TestGetUser:
    async def test_get_by_id(self, client):
        headers = await register_and_login(client, "user-123")
        resp = await client.get("/api/users/user-123", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == "user-123"

    async def test_other_user_gets_403(self, client):
        await _create_user(client, "user-123")
        headers = await register_and_login(client, "someone-else")
        resp = await client.get("/api/users/user-123", headers=headers)
        assert resp.status_code == 403

    async def test_nonexistent_returns_403_before_404(self, client):
        # Ownership is checked before existence, so a non-owner gets 403 even
        # for a user_id that doesn't exist — avoids leaking which ids are registered.
        headers = await register_and_login(client, "user-123")
        resp = await client.get("/api/users/does-not-exist", headers=headers)
        assert resp.status_code == 403


class TestUpdateUser:
    async def test_deactivate_user(self, client):
        headers = await register_and_login(client, "user-123")
        resp = await client.put("/api/users/user-123", json={"active": False}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["active"] is False

    async def test_change_password(self, client):
        headers = await register_and_login(client, "user-123", "old-pass")
        resp = await client.put(
            "/api/users/user-123", json={"password": "new-pass"}, headers=headers
        )
        assert resp.status_code == 200

        login_old = await client.post(
            "/api/auth/login", data={"username": "user-123", "password": "old-pass"}
        )
        assert login_old.status_code == 401

        login_new = await client.post(
            "/api/auth/login", data={"username": "user-123", "password": "new-pass"}
        )
        assert login_new.status_code == 200

    async def test_other_user_gets_403(self, client):
        await _create_user(client, "user-123")
        headers = await register_and_login(client, "someone-else")
        resp = await client.put("/api/users/user-123", json={"active": False}, headers=headers)
        assert resp.status_code == 403


class TestDeleteUser:
    async def test_delete_returns_204(self, client):
        headers = await register_and_login(client, "user-123")
        resp = await client.delete("/api/users/user-123", headers=headers)
        assert resp.status_code == 204

    async def test_deleted_user_is_gone(self, client):
        headers = await register_and_login(client, "user-123")
        await client.delete("/api/users/user-123", headers=headers)
        resp = await client.get("/api/users/user-123", headers=headers)
        assert resp.status_code == 401  # token's user no longer exists

    async def test_other_user_gets_403(self, client):
        await _create_user(client, "user-123")
        headers = await register_and_login(client, "someone-else")
        resp = await client.delete("/api/users/user-123", headers=headers)
        assert resp.status_code == 403
