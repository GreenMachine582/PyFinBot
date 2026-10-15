"""HTML error pages (greentechhub-fastapi v0.17's register_error_pages):
browser page requests get greentechhub-ui's 404/403/500 pages, while /api and
htmx requests keep the JSON envelope or FastAPI's default."""

import httpx
import pytest

from pyfinbot.pyfinbot import app

from .conftest import web_login

HTML = {"Accept": "text/html"}
BOOM = "/__test-error-pages-boom"


async def test_a_missing_page_renders_the_404_page(gth_client):
    page = await gth_client.get("/nope", headers=HTML)
    assert page.status_code == 404
    assert "text/html" in page.headers["content-type"]
    assert "gth-error-page" in page.text and "Page not found" in page.text


async def test_the_api_keeps_its_json_envelope(gth_client):
    api = await gth_client.get("/api/nope", headers=HTML)
    assert api.status_code == 404 and api.json()["code"] == "not_found"


async def test_htmx_requests_keep_json(gth_client):
    resp = await gth_client.get("/nope", headers={**HTML, "HX-Request": "true"})
    assert resp.status_code == 404 and resp.json() == {"detail": "Not Found"}


async def test_a_missing_stock_page_shows_its_message(gth_client):
    await web_login(gth_client, "errors-stock")
    page = await gth_client.get("/stocks/999999/edit", headers=HTML)
    assert page.status_code == 404 and "gth-error-page" in page.text


async def test_a_signed_in_user_without_permission_gets_the_403_page(gth_client):
    await web_login(gth_client, "errors-viewer")
    page = await gth_client.get("/admin/roles", headers=HTML)
    assert page.status_code == 403 and "gth-error-page" in page.text


@pytest.fixture
def boom_route():
    async def boom():
        raise RuntimeError("kaboom")

    app.add_api_route(BOOM, boom, methods=["GET"])
    yield
    app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", None) != BOOM]


async def test_an_unhandled_error_renders_the_500_page_with_its_reference(boom_route):
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
        page = await client.get(BOOM, headers={**HTML, "X-Request-ID": "req-errors-1"})
    assert page.status_code == 500
    assert "gth-error-page" in page.text and "req-errors-1" in page.text
