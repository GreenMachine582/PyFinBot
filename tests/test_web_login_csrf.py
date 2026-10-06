"""CSRF on the sign-in form (greentechhub adoption, item 6): csrf = True on
PyFinBotLoginViews, fastapi's double-submit gth_csrf cookie and ui's hidden
csrf_token field."""
import re

from greentechhub_core.security import account_key
from httpx import AsyncClient

from pyfinbot.core.login_throttle import LOGIN_THROTTLE

from .conftest import create_user, post_login

HTML = {"Accept": "text/html"}
REFUSED = "Your session expired. Please try again."


async def test_the_sign_in_page_carries_a_token_and_sets_its_cookie(client: AsyncClient):
    resp = await client.get("/login", headers=HTML)
    assert resp.status_code == 200
    token = resp.cookies["gth_csrf"]
    assert re.search(rf'name="csrf_token"[^>]*value="{re.escape(token)}"', resp.text) \
        or re.search(rf'value="{re.escape(token)}"[^>]*name="csrf_token"', resp.text)


async def test_a_post_without_the_token_is_refused(client: AsyncClient):
    await create_user(client, "csrf-a")
    resp = await client.post("/login", data={"user_id": "csrf-a", "password": "hunter2!"},
                             follow_redirects=False)
    assert resp.status_code == 403
    assert REFUSED in resp.text
    assert "gth_session" not in resp.headers.get("set-cookie", "")


async def test_a_wrong_token_is_refused(client: AsyncClient):
    await create_user(client, "csrf-b")
    page = await client.get("/login", headers=HTML)
    client.cookies.set("gth_csrf", page.cookies["gth_csrf"])
    resp = await client.post("/login", follow_redirects=False, data={
        "user_id": "csrf-b", "password": "hunter2!", "csrf_token": "not-the-token-but-long-enough"})
    assert resp.status_code == 403
    assert REFUSED in resp.text


async def test_a_refused_post_isnt_a_failed_sign_in(client: AsyncClient):
    # The check runs before the throttle: a forged request can't lock anyone out.
    await create_user(client, "csrf-c")
    for _ in range(6):
        await client.post("/login", data={"user_id": "csrf-c", "password": "wrong"})
    assert (await LOGIN_THROTTLE.check(account_key("csrf-c"))).failures == 0
    resp = await post_login(client, "csrf-c", "hunter2!", follow_redirects=False)
    assert resp.status_code == 303


async def test_the_token_signs_in(client: AsyncClient):
    await create_user(client, "csrf-d")
    resp = await post_login(client, "csrf-d", "hunter2!", follow_redirects=False)
    assert resp.status_code == 303 and resp.headers["location"] == "/"
    assert "gth_session" in resp.cookies


async def test_the_api_login_needs_no_token(client: AsyncClient):
    # A bearer-token endpoint, not a cookie form: nothing for CSRF to protect.
    await create_user(client, "csrf-e")
    resp = await client.post("/api/auth/login", data={"username": "csrf-e", "password": "hunter2!"})
    assert resp.status_code == 200 and resp.json()["access_token"]
