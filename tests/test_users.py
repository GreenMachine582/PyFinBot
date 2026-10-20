"""Integration tests for /api/users routes (core/users.py's USER_STORE).
Paths take the account id. Creating and listing users need users.manage
(the admin role); get/update/delete are self-only, and delete deactivates."""

from .conftest import create_user, make_admin, register_and_login, user_id


async def _admin_headers(client, username="admin-1"):
    headers = await register_and_login(client, username)
    await make_admin(client, username)
    return headers


NEW = {"username": "user-123", "password": "hunter2!"}


class TestCreateUser:
    async def test_admin_creates_and_returns_user(self, gth_client):
        headers = await _admin_headers(gth_client)
        resp = await gth_client.post("/api/users/", json={**NEW, "email": "U@example.com",
                                                          "display_name": "User One"},
                                     headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["id"]) == 32 and data["id"] == await user_id("user-123")
        assert (data["username"], data["email"], data["email_verified"], data["display_name"]) == (
            "user-123", "u@example.com", False, "User One")
        assert data["active"] is True and data["auth_source"] == "local"
        assert "created_at" in data and data["last_login_at"] is None
        assert "password" not in data and "password_hash" not in data
        login = await gth_client.post("/api/auth/login", data={"username": "user-123", "password": "hunter2!"})
        assert login.status_code == 200

    async def test_duplicate_username_or_email_returns_400(self, gth_client):
        headers = await _admin_headers(gth_client)
        await create_user(gth_client, "user-123")
        resp = await gth_client.post("/api/users/", json=NEW, headers=headers)
        assert resp.status_code == 400 and resp.json()["code"] == "user_exists"
        assert resp.json()["details"] == {"field": "username"}
        await gth_client.post("/api/users/", json={**NEW, "username": "u2", "email": "a@example.com"},
                              headers=headers)
        taken = await gth_client.post("/api/users/", json={**NEW, "username": "u3", "email": "A@example.com"},
                                      headers=headers)
        assert taken.status_code == 400 and taken.json()["details"] == {"field": "email"}

    async def test_a_bad_username_or_email_returns_400(self, gth_client):
        headers = await _admin_headers(gth_client)
        for body in ({**NEW, "username": "two words"}, {**NEW, "email": "not-an-email"}):
            resp = await gth_client.post("/api/users/", json=body, headers=headers)
            assert resp.status_code == 400 and resp.json()["code"] == "invalid_user"

    async def test_missing_password_returns_422(self, gth_client):
        headers = await _admin_headers(gth_client)
        resp = await gth_client.post("/api/users/", json={"username": "user-123"}, headers=headers)
        assert resp.status_code == 422

    async def test_no_open_registration(self, gth_client):
        resp = await gth_client.post("/api/users/", json=NEW)
        assert resp.status_code == 401

    async def test_non_admin_gets_403(self, gth_client):
        headers = await register_and_login(gth_client, "plain-user")
        resp = await gth_client.post("/api/users/", json=NEW, headers=headers)
        assert resp.status_code == 403


class TestListUsers:
    async def test_admin_gets_every_user(self, gth_client):
        await create_user(gth_client, "u1")
        await create_user(gth_client, "u2")
        headers = await _admin_headers(gth_client, "u3")
        resp = await gth_client.get("/api/users/", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert {"u1", "u2", "u3"} <= {u["username"] for u in data}

    async def test_non_admin_gets_403(self, gth_client):
        headers = await register_and_login(gth_client, "plain-user")
        resp = await gth_client.get("/api/users/", headers=headers)
        assert resp.status_code == 403

    async def test_no_token_returns_401(self, gth_client):
        resp = await gth_client.get("/api/users/")
        assert resp.status_code == 401


class TestMe:
    async def test_me_is_the_signed_in_account(self, gth_client):
        headers = await register_and_login(gth_client, "user-123")
        resp = await gth_client.get("/api/auth/me", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == await user_id("user-123")
        assert resp.json()["last_login_at"] is not None

    async def test_me_needs_a_token(self, gth_client):
        assert (await gth_client.get("/api/auth/me")).status_code == 401


class TestGetUser:
    async def test_get_by_id(self, gth_client):
        headers = await register_and_login(gth_client, "user-123")
        me = await user_id("user-123")
        resp = await gth_client.get(f"/api/users/{me}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["username"] == "user-123"

    async def test_other_user_gets_403(self, gth_client):
        other = await create_user(gth_client, "user-123")
        headers = await register_and_login(gth_client, "someone-else")
        resp = await gth_client.get(f"/api/users/{other}", headers=headers)
        assert resp.status_code == 403

    async def test_nonexistent_returns_403_before_404(self, gth_client):
        # Ownership is checked before existence, so a non-owner gets 403 even
        # for an id that doesn't exist — avoids leaking which ids are registered.
        headers = await register_and_login(gth_client, "user-123")
        resp = await gth_client.get("/api/users/" + "0" * 32, headers=headers)
        assert resp.status_code == 403


class TestUpdateUser:
    async def test_profile_and_deactivation(self, gth_client):
        headers = await register_and_login(gth_client, "user-123")
        me = await user_id("user-123")
        resp = await gth_client.put(f"/api/users/{me}", json={"display_name": "Me", "email": "me@example.com"},
                                    headers=headers)
        assert resp.status_code == 200
        assert (resp.json()["display_name"], resp.json()["email"]) == ("Me", "me@example.com")
        resp = await gth_client.put(f"/api/users/{me}", json={"active": False}, headers=headers)
        assert resp.status_code == 200 and resp.json()["active"] is False
        # Deactivated: the same token no longer signs anyone in.
        assert (await gth_client.get(f"/api/users/{me}", headers=headers)).status_code == 401

    async def test_a_taken_email_returns_400(self, gth_client):
        await create_user(gth_client, "other")
        other = await register_and_login(gth_client, "other-two")
        await gth_client.put(f"/api/users/{await user_id('other-two')}", json={"email": "x@example.com"},
                             headers=other)
        headers = await register_and_login(gth_client, "user-123")
        resp = await gth_client.put(f"/api/users/{await user_id('user-123')}",
                                    json={"email": "X@example.com"}, headers=headers)
        assert resp.status_code == 400 and resp.json()["details"] == {"field": "email"}

    async def test_change_password(self, gth_client):
        headers = await register_and_login(gth_client, "user-123", "old-pass")
        me = await user_id("user-123")
        resp = await gth_client.put(f"/api/users/{me}", json={"password": "new-pass"}, headers=headers)
        assert resp.status_code == 200

        login_old = await gth_client.post(
            "/api/auth/login", data={"username": "user-123", "password": "old-pass"}
        )
        assert login_old.status_code == 401

        login_new = await gth_client.post(
            "/api/auth/login", data={"username": "user-123", "password": "new-pass"}
        )
        assert login_new.status_code == 200

    async def test_other_user_gets_403(self, gth_client):
        other = await create_user(gth_client, "user-123")
        headers = await register_and_login(gth_client, "someone-else")
        resp = await gth_client.put(f"/api/users/{other}", json={"active": False}, headers=headers)
        assert resp.status_code == 403


class TestDeleteUser:
    async def test_delete_deactivates_and_signs_out(self, gth_client):
        headers = await register_and_login(gth_client, "user-123")
        me = await user_id("user-123")
        resp = await gth_client.delete(f"/api/users/{me}", headers=headers)
        assert resp.status_code == 204
        # The token hasn't expired, but the account is inactive, so it's refused.
        assert (await gth_client.get(f"/api/users/{me}", headers=headers)).status_code == 401
        login = await gth_client.post("/api/auth/login", data={"username": "user-123", "password": "hunter2!"})
        assert login.status_code == 401

    async def test_other_user_gets_403(self, gth_client):
        other = await create_user(gth_client, "user-123")
        headers = await register_and_login(gth_client, "someone-else")
        resp = await gth_client.delete(f"/api/users/{other}", headers=headers)
        assert resp.status_code == 403
