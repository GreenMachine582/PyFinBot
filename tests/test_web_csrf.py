"""CSRF on the in-app forms (greentechhub-fastapi v0.16's register_csrf /
require_csrf): every state-changing page route, the settings and role views
and POST /logout need the gth_csrf cookie's token back as X-CSRF-Token,
which ui v0.17's app shell sends on every htmx request (hx-headers)."""
import io
import json
import re

import pytest

from .conftest import create_stock, make_admin, web_login

HX = {"HX-Request": "true"}
REFUSED = "Your session expired. Please try again."


def _requests(stock_id: int) -> list[tuple[str, str, dict]]:
    return [
        ("POST", "/stocks", {"data": {"market": "ASX", "symbol": "CSRF", "name": "Csrf Co"}}),
        ("DELETE", f"/stocks/{stock_id}", {}),
        ("POST", "/transactions/bulk-delete", {"data": {"ids": "1"}}),
        ("POST", "/import", {"files": {"file": ("t.csv", io.BytesIO(b""), "text/csv")}}),
        ("POST", "/emails/sync", {}),
        ("POST", "/dividends/sync", {}),
        ("POST", "/settings/preferences", {"data": {"ui.page_size": "10"}}),
        ("POST", "/admin/roles", {"data": {"subject": "csrf-other", "role": "admin"}}),
        ("POST", "/logout", {}),
    ]


async def test_state_changing_routes_refuse_a_missing_token(gth_client):
    await web_login(gth_client, "csrf-user")
    await make_admin(gth_client, "csrf-user")
    stock = await create_stock(gth_client, "CSRF", "ASX", "Csrf Co")
    token = gth_client.headers.pop("X-CSRF-Token")
    for method, url, kwargs in _requests(stock["id"]):
        resp = await gth_client.request(method, url, headers=HX, follow_redirects=False, **kwargs)
        assert resp.status_code == 403, (method, url, resp.status_code)
        assert REFUSED in resp.text, (method, url)
    # A wrong token is refused too.
    resp = await gth_client.post("/stocks", headers={**HX, "X-CSRF-Token": token[::-1]},
                                 data={"market": "ASX", "symbol": "CSRF2", "name": "x"})
    assert resp.status_code == 403


async def test_with_the_token_they_go_through(gth_client):
    await web_login(gth_client, "csrf-ok")
    await make_admin(gth_client, "csrf-ok")
    stock = await create_stock(gth_client, "CSRF", "ASX", "Csrf Co")
    for method, url, kwargs in _requests(stock["id"]):
        resp = await gth_client.request(method, url, headers=HX, follow_redirects=False, **kwargs)
        assert resp.status_code != 403, (method, url, resp.text)


@pytest.mark.parametrize("url", ["/stocks", "/transactions/bulk-delete", "/import", "/emails/sync"])
async def test_signed_out_still_bounces_to_login(gth_client, url):
    resp = await gth_client.post(url, headers=HX, follow_redirects=False)
    assert resp.status_code == 401 and resp.headers["HX-Redirect"] == "/login"


async def test_pages_send_the_token_with_htmx(gth_client):
    await web_login(gth_client, "csrf-page")
    page = (await gth_client.get("/", headers={"Accept": "text/html"})).text
    headers = json.loads(re.search(r"<body hx-headers='([^']+)'", page).group(1))
    assert headers == {"X-CSRF-Token": gth_client.headers["X-CSRF-Token"]}
