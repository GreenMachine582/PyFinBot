"""Login throttling (greentechhub adoption, item 5): core's LoginThrottle over
gth_login_attempts on the web sign-in form, and TRUSTED_PROXIES so each
client behind the reverse proxy is counted by its own address."""

from greentechhub_core.security import account_key, client_key
from httpx import AsyncClient

from pyfinbot.core.login_throttle import LOGIN_THROTTLE

from .conftest import create_user, post_login

LOCKED = "Too many failed sign-ins"
CLIENT = "127.0.0.1"  # httpx's ASGITransport client address


async def _web(client: AsyncClient, user_id: str, password: str):
    return await post_login(client, user_id, password,
                             follow_redirects=False)


async def test_fifth_wrong_password_locks_the_web_form(gth_client: AsyncClient):
    await create_user(gth_client, "throttle-a")
    for _ in range(4):
        assert (await _web(gth_client, "throttle-a", "wrong-pass")).status_code == 401

    resp = await _web(gth_client, "throttle-a", "wrong-pass")
    assert resp.status_code == 429
    assert LOCKED in resp.text and "15 minutes" in resp.text
    assert 0 < int(resp.headers["Retry-After"]) <= 15 * 60

    # Locked out: even the right password is refused, without a session.
    resp = await _web(gth_client, "throttle-a", "hunter2!")
    assert resp.status_code == 429
    assert "gth_session" not in resp.headers.get("set-cookie", "")


async def test_a_good_sign_in_clears_the_accounts_count(gth_client: AsyncClient):
    await create_user(gth_client, "throttle-b")
    for _ in range(4):
        assert (await _web(gth_client, "throttle-b", "wrong-pass")).status_code == 401
    assert (await _web(gth_client, "throttle-b", "hunter2!")).status_code == 303

    # The account's count is cleared; the client's is kept, so one good
    # login can't reset a guesser who also owns an account.
    assert (await LOGIN_THROTTLE.check(account_key("throttle-b"))).failures == 0
    assert (await LOGIN_THROTTLE.check(client_key(CLIENT))).failures == 4


async def test_one_client_guessing_many_accounts_is_locked_out(gth_client: AsyncClient):
    for n in range(5):
        resp = await _web(gth_client, f"nobody-{n}", "wrong-pass")
    assert resp.status_code == 429  # the client key reached 5 across accounts

    await create_user(gth_client, "throttle-e")
    assert (await _web(gth_client, "throttle-e", "hunter2!")).status_code == 429


async def test_trusted_proxies_gives_each_forwarded_client_its_own_address(monkeypatch):
    # TRUSTED_PROXIES must reach register_core through PyFinBot's Settings (now
    # core's GTHBaseSettings.trusted_proxies; extra="ignore" would drop an
    # undeclared one), so the throttle's client key is the real client's.
    from fastapi import FastAPI, Request
    from greentechhub_fastapi import register_core
    from httpx import ASGITransport

    from pyfinbot.core.settings import Settings

    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.5")
    app = FastAPI()
    register_core(app, Settings())

    @app.get("/whoami")
    async def whoami(request: Request):
        return request.client.host if request.client else None

    async def seen(peer: str) -> str:
        transport = ASGITransport(app=app, client=(peer, 1234))
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/whoami", headers={"X-Forwarded-For": "203.0.113.9"})
            return resp.json()

    assert await seen("10.0.0.5") == "203.0.113.9"  # via the proxy: the real client
    assert await seen("198.51.100.7") == "198.51.100.7"  # anyone else can't spoof it
