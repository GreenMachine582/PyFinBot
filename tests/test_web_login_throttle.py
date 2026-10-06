"""Login throttling (greentechhub adoption, item 5): core's LoginThrottle over
gth_login_attempts, shared by the web sign-in form and /api/auth/login."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from greentechhub_core.security import account_key, client_key
from httpx import AsyncClient

from pyfinbot.core.login_throttle import LOGIN_THROTTLE

from .conftest import create_user

ROOT = Path(__file__).resolve().parents[1]
LOCKED = "Too many failed sign-ins"
CLIENT = "127.0.0.1"  # httpx's ASGITransport client address


async def _web(client: AsyncClient, user_id: str, password: str):
    return await client.post("/login", data={"user_id": user_id, "password": password},
                             follow_redirects=False)


async def _api(client: AsyncClient, user_id: str, password: str):
    return await client.post("/api/auth/login", data={"username": user_id, "password": password})


async def test_fifth_wrong_password_locks_the_web_form(client: AsyncClient):
    await create_user(client, "throttle-a")
    for _ in range(4):
        assert (await _web(client, "throttle-a", "wrong-pass")).status_code == 401

    resp = await _web(client, "throttle-a", "wrong-pass")
    assert resp.status_code == 429
    assert LOCKED in resp.text and "15 minutes" in resp.text
    assert 0 < int(resp.headers["Retry-After"]) <= 15 * 60

    # Locked out: even the right password is refused, without a session.
    resp = await _web(client, "throttle-a", "hunter2!")
    assert resp.status_code == 429
    assert "gth_session" not in resp.headers.get("set-cookie", "")


async def test_a_good_sign_in_clears_the_accounts_count(client: AsyncClient):
    await create_user(client, "throttle-b")
    for _ in range(4):
        assert (await _web(client, "throttle-b", "wrong-pass")).status_code == 401
    assert (await _web(client, "throttle-b", "hunter2!")).status_code == 303

    # The account's count is cleared; the client's is kept, so one good
    # login can't reset a guesser who also owns an account.
    assert (await LOGIN_THROTTLE.check(account_key("throttle-b"))).failures == 0
    assert (await LOGIN_THROTTLE.check(client_key(CLIENT))).failures == 4


async def test_web_lockout_also_locks_the_api(client: AsyncClient):
    await create_user(client, "throttle-c")
    for _ in range(5):
        await _web(client, "throttle-c", "wrong-pass")

    resp = await _api(client, "throttle-c", "hunter2!")
    assert resp.status_code == 429
    assert resp.json()["code"] == "http_429"
    assert resp.json()["message"].startswith(LOCKED)
    assert int(resp.headers["Retry-After"]) > 0


async def test_api_failures_lock_the_web_form(client: AsyncClient):
    await create_user(client, "throttle-d")
    for _ in range(4):
        resp = await _api(client, "throttle-d", "wrong-pass")
        assert resp.status_code == 401
        assert resp.headers["WWW-Authenticate"] == "Bearer"
    assert (await _api(client, "throttle-d", "wrong-pass")).status_code == 429

    resp = await _web(client, "throttle-d", "hunter2!")
    assert resp.status_code == 429 and LOCKED in resp.text


async def test_one_client_guessing_many_accounts_is_locked_out(client: AsyncClient):
    for n in range(5):
        resp = await _web(client, f"nobody-{n}", "wrong-pass")
    assert resp.status_code == 429  # the client key reached 5 across accounts

    await create_user(client, "throttle-e")
    assert (await _web(client, "throttle-e", "hunter2!")).status_code == 429


def test_migration_creates_and_drops_gth_login_attempts(tmp_path):
    db = tmp_path / "migrate.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db}",
           "ASYNC_DATABASE_URL": f"sqlite+aiosqlite:///{db}"}

    def alembic(*args):
        # A subprocess: alembic's env.py imports the models as src.pyfinbot,
        # which would redefine this process's tables.
        subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, check=True,
                       capture_output=True)

    def tables():
        with sqlite3.connect(db) as conn:
            return {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}

    alembic("upgrade", "head")
    with sqlite3.connect(db) as conn:
        cols = [r[1] for r in conn.execute("pragma table_info(gth_login_attempts)")]
    assert cols == ["key", "failures", "window_start", "locked_until"]
    alembic("downgrade", "d52e9f3a8b17")  # back to before gth_login_attempts
    assert "gth_login_attempts" not in tables() and "gth_role_grants" in tables()
