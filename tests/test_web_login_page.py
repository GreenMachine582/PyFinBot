"""The login page after the greentechhub ui v0.14 / fastapi v0.11 bump:
fastapi's LoginViews renders greentechhub-ui's login_page.html by default, so
PyFinBot no longer ships its own login.html."""
from httpx import AsyncClient

from .conftest import create_user, make_admin, web_login

HTML = {"Accept": "text/html"}
HX = {"HX-Request": "true"}


async def test_login_is_greentechhub_uis_sign_in_page(client: AsyncClient):
    resp = await client.get("/login", headers=HTML)
    assert resp.status_code == 200
    page = resp.text
    assert '<main class="gth-auth">' in page  # layout="auth"
    assert "gth-navbar" not in page  # no app nav for a signed-out visitor
    assert "Sign in" in page and "to PyFinBot" in page
    assert '<div class="gth-auth-service">PyFinBot</div>' in page
    assert 'action="/login"' in page and 'name="user_id"' in page and 'name="password"' in page


async def test_wrong_password_keeps_the_user_id_but_not_the_password(client: AsyncClient):
    await create_user(client, "login-a")
    resp = await client.post("/login", data={"user_id": "login-a", "password": "not-it-123"})
    assert resp.status_code == 401
    assert "gth-toast-inline gth-toast-danger" in resp.text
    assert "Incorrect user ID or password" in resp.text
    assert 'value="login-a"' in resp.text
    assert "not-it-123" not in resp.text


async def test_sign_in_still_lands_on_the_dashboard(client: AsyncClient):
    await create_user(client, "login-b")
    resp = await client.post("/login", data={"user_id": "login-b", "password": "hunter2!"},
                             follow_redirects=False)
    assert resp.status_code == 303 and resp.headers["location"] == "/"
    assert "gth_session" in resp.headers.get("set-cookie", "")


async def test_site_banner_shows_once_on_the_login_page(client: AsyncClient):
    # fastapi's settings_context emits the banner (core's site_banner_settings);
    # signed out, the login page still shows it, once.
    await web_login(client, "login-admin")
    await make_admin(client, "login-admin")
    resp = await client.post("/settings/app", headers=HX, data={
        "site.banner": "Maintenance tonight 22:00", "site.banner_tone": "bad"})
    assert resp.status_code == 200, resp.text
    client.cookies.clear()  # signed out

    page = (await client.get("/login", headers=HTML)).text
    assert page.count('data-gth-banner="site"') == 1
    assert "Maintenance tonight 22:00" in page
