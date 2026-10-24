"""The API's bearer auth is greentechhub-fastapi's (v0.15): register_auth(...,
bearer=True), issue_token at /api/auth/login and bearer_scheme in OpenAPI, in
place of core/security.py and core/dependencies.py. API routes take an
Identity."""
import base64
import importlib
import json
import time

import pytest

from .conftest import register_and_login, user_id, web_login

# The module, not core/__init__'s `settings` object of the same name.
settings_module = importlib.import_module("pyfinbot.core.settings")

REPORT = "/api/reports/dividends?fy=2024"


def _claims(token: str) -> dict:
    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


async def test_a_login_token_authorises_the_api(gth_client):
    headers = await register_and_login(gth_client, "bearer-alice")
    resp = await gth_client.get(REPORT, headers=headers)
    assert resp.status_code == 200, resp.text


async def test_a_login_token_lasts_24_hours(gth_client):
    headers = await register_and_login(gth_client, "bearer-bob")
    claims = _claims(headers["Authorization"].removeprefix("Bearer "))
    assert claims["sub"] == await user_id("bearer-bob")
    assert abs(claims["exp"] - (time.time() + 24 * 3600)) < 120


async def test_a_bad_token_never_falls_back_to_the_cookie(gth_client):
    await web_login(gth_client, "bearer-carol")
    assert (await gth_client.get(REPORT)).status_code == 200  # the cookie alone works
    resp = await gth_client.get(REPORT, headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401
    assert resp.headers["WWW-Authenticate"] == "Bearer"


async def test_routes_scope_to_the_tokens_subject(gth_client):
    alice = await register_and_login(gth_client, "bearer-dan")
    await register_and_login(gth_client, "bearer-erin")
    dan, erin = await user_id("bearer-dan"), await user_id("bearer-erin")
    assert (await gth_client.get(f"/api/users/{dan}", headers=alice)).status_code == 200
    assert (await gth_client.get(f"/api/users/{erin}", headers=alice)).status_code == 403


async def test_openapi_documents_the_token_flow(gth_client):
    schemes = (await gth_client.get("/openapi.json")).json()["components"]["securitySchemes"]
    flows = [s["flows"]["password"]["tokenUrl"] for s in schemes.values() if s["type"] == "oauth2"]
    assert flows == ["/api/auth/login"]


def test_access_token_expire_minutes_is_retired(monkeypatch):
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    with pytest.warns(UserWarning, match="ACCESS_TOKEN_EXPIRE_MINUTES is no longer used: API tokens last 24 hours"):
        settings_module.Settings(secret_key="k", _env_file=None)
