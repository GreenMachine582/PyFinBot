from __future__ import annotations

from httpx import AsyncClient

from pyfinbot.core.settings import settings

from .conftest import create_user, post_login, send_csrf


async def _register(client: AsyncClient, user_id: str, password: str = "hunter2!") -> None:
    await create_user(client, user_id, password)


async def test_login_form_renders(gth_client: AsyncClient):
    resp = await gth_client.get("/login")
    assert resp.status_code == 200
    assert "Sign in" in resp.text  # greentechhub-ui's login_page.html (fastapi v0.11)


async def test_dashboard_redirects_when_not_logged_in(gth_client: AsyncClient):
    resp = await gth_client.get("/", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


async def test_login_wrong_password_shows_error(gth_client: AsyncClient):
    await _register(gth_client, "weba")
    resp = await post_login(gth_client, "weba", "wrong")
    assert resp.status_code == 401
    assert "Incorrect user ID or password" in resp.text


async def test_login_unknown_user_shows_error(gth_client: AsyncClient):
    resp = await post_login(gth_client, "nobody", "wrong")
    assert resp.status_code == 401
    assert "Incorrect user ID or password" in resp.text


async def test_login_success_sets_session_cookie_and_dashboard_loads(gth_client: AsyncClient):
    await _register(gth_client, "webb")
    resp = await post_login(gth_client, "webb", "hunter2!", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
    assert "gth_session" in resp.cookies

    resp2 = await gth_client.get("/", cookies={"gth_session": resp.cookies["gth_session"]})
    assert resp2.status_code == 200
    assert "Dashboard" in resp2.text
    assert "webb" in resp2.text


async def test_logout_clears_session(gth_client: AsyncClient):
    await _register(gth_client, "webc")
    login_resp = await post_login(gth_client, "webc", "hunter2!", follow_redirects=False)
    cookie = login_resp.cookies["gth_session"]
    send_csrf(gth_client)  # POST /logout checks it (logout_csrf)

    logout_resp = await gth_client.post(
        "/logout", cookies={"gth_session": cookie}, follow_redirects=False
    )
    assert logout_resp.status_code == 303
    assert logout_resp.headers["location"] == "/login"


def test_build_router_returns_none_for_non_local_adapter(monkeypatch):
    from pyfinbot.web.routes import auth as web_auth_module

    monkeypatch.setattr(settings, "auth_adapter", "forward_auth")
    assert web_auth_module.build_router() is None
