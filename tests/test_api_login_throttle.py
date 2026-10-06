"""API login throttling (item 7): /api/auth/login shares the web sign-in
form's LoginThrottle through greentechhub-fastapi's throttled_login."""
from httpx import AsyncClient

from .conftest import create_user

LOCKED = "Too many failed sign-ins"


async def _web(client: AsyncClient, user_id: str, password: str):
    return await client.post("/login", data={"user_id": user_id, "password": password},
                             follow_redirects=False)


async def _api(client: AsyncClient, user_id: str, password: str):
    return await client.post("/api/auth/login", data={"username": user_id, "password": password})


async def test_failures_below_the_limit_are_a_bearer_401(client: AsyncClient):
    await create_user(client, "api-throttle-a")
    resp = await _api(client, "api-throttle-a", "wrong-pass")
    assert resp.status_code == 401
    assert resp.headers["WWW-Authenticate"] == "Bearer"


async def test_fifth_wrong_password_locks_the_api(client: AsyncClient):
    await create_user(client, "api-throttle-b")
    for _ in range(4):
        assert (await _api(client, "api-throttle-b", "wrong-pass")).status_code == 401

    resp = await _api(client, "api-throttle-b", "wrong-pass")
    assert resp.status_code == 429
    assert resp.json()["code"] == "too_many_requests"
    assert resp.json()["message"] == f"{LOCKED}. Try again in 15 minutes."
    assert 0 < int(resp.headers["Retry-After"]) <= 15 * 60

    # Locked out: even the right password gets no token.
    resp = await _api(client, "api-throttle-b", "hunter2!")
    assert resp.status_code == 429 and "access_token" not in resp.text


async def test_a_web_lockout_also_locks_the_api(client: AsyncClient):
    await create_user(client, "api-throttle-c")
    for _ in range(5):
        await _web(client, "api-throttle-c", "wrong-pass")
    assert (await _api(client, "api-throttle-c", "hunter2!")).status_code == 429


async def test_an_api_lockout_also_locks_the_web_form(client: AsyncClient):
    await create_user(client, "api-throttle-d")
    for _ in range(5):
        await _api(client, "api-throttle-d", "wrong-pass")
    resp = await _web(client, "api-throttle-d", "hunter2!")
    assert resp.status_code == 429 and LOCKED in resp.text


async def test_a_good_api_login_still_issues_a_token(client: AsyncClient):
    await create_user(client, "api-throttle-e")
    resp = await _api(client, "api-throttle-e", "hunter2!")
    assert resp.status_code == 200
    assert resp.json()["token_type"] == "bearer" and resp.json()["access_token"]
