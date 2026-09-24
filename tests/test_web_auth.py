from __future__ import annotations

from httpx import AsyncClient

from pyfinbot.core.settings import settings


async def _register(client: AsyncClient, user_id: str, password: str = "hunter2!") -> None:
    resp = await client.post("/api/users/", json={"id": user_id, "password": password})
    assert resp.status_code == 201, resp.text


async def test_login_form_renders(client: AsyncClient):
    resp = await client.get("/login")
    assert resp.status_code == 200
    assert "Log in" in resp.text


async def test_dashboard_redirects_when_not_logged_in(client: AsyncClient):
    resp = await client.get("/", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


async def test_login_wrong_password_shows_error(client: AsyncClient):
    await _register(client, "weba")
    resp = await client.post("/login", data={"user_id": "weba", "password": "wrong"})
    assert resp.status_code == 401
    assert "Incorrect user ID or password" in resp.text


async def test_login_unknown_user_shows_error(client: AsyncClient):
    resp = await client.post("/login", data={"user_id": "nobody", "password": "wrong"})
    assert resp.status_code == 401
    assert "Incorrect user ID or password" in resp.text


async def test_login_success_sets_session_cookie_and_dashboard_loads(client: AsyncClient):
    await _register(client, "webb")
    resp = await client.post(
        "/login",
        data={"user_id": "webb", "password": "hunter2!"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
    assert "gth_session" in resp.cookies

    resp2 = await client.get("/", cookies={"gth_session": resp.cookies["gth_session"]})
    assert resp2.status_code == 200
    assert "Dashboard" in resp2.text
    assert "webb" in resp2.text


async def test_logout_clears_session(client: AsyncClient):
    await _register(client, "webc")
    login_resp = await client.post(
        "/login",
        data={"user_id": "webc", "password": "hunter2!"},
        follow_redirects=False,
    )
    cookie = login_resp.cookies["gth_session"]

    logout_resp = await client.post(
        "/logout", cookies={"gth_session": cookie}, follow_redirects=False
    )
    assert logout_resp.status_code == 303
    assert logout_resp.headers["location"] == "/login"


def test_build_router_returns_none_for_non_local_adapter(monkeypatch):
    from pyfinbot.web.routes import auth as web_auth_module

    monkeypatch.setattr(settings, "AUTH_ADAPTER", "forward_auth")
    assert web_auth_module.build_router() is None
