"""CSRF on the API for cookie-authenticated calls (greentechhub-fastapi
v0.17's require_cookie_csrf on the /api routers): a browser's session cookie
works on /api, so a state-changing call it signs in needs the CSRF token;
bearer-token scripts and anonymous calls (POST /api/auth/login) need none."""

from .conftest import register_and_login, web_login

STOCK = {"symbol": "CSRF", "market": "ASX", "name": "Csrf Co"}


async def test_a_cookie_post_needs_the_token(gth_client):
    await web_login(gth_client, "api-csrf-cookie")
    token = gth_client.headers.pop("X-CSRF-Token")  # web_login sends it, as the app shell does
    refused = await gth_client.post("/api/stocks/", json=STOCK)
    assert refused.status_code == 403
    allowed = await gth_client.post("/api/stocks/", json=STOCK, headers={"X-CSRF-Token": token})
    assert allowed.status_code == 201, allowed.text


async def test_a_cookie_get_needs_no_token(gth_client):
    await web_login(gth_client, "api-csrf-get")
    gth_client.headers.pop("X-CSRF-Token")
    assert (await gth_client.get("/api/stocks/")).status_code == 200


async def test_a_bearer_post_needs_no_token(gth_client):
    headers = await register_and_login(gth_client, "api-csrf-bearer")
    assert "X-CSRF-Token" not in gth_client.headers
    resp = await gth_client.post("/api/stocks/", json={**STOCK, "symbol": "BEAR"}, headers=headers)
    assert resp.status_code == 201, resp.text


async def test_logging_in_through_the_api_still_works(gth_client):
    # register_and_login posts the OAuth2 form anonymously, with no CSRF token.
    headers = await register_and_login(gth_client, "api-csrf-login")
    assert headers["Authorization"].startswith("Bearer ")
