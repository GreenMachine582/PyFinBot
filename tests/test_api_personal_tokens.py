"""Personal API tokens (greentechhub-core v0.15's token store, greentechhub-fastapi
v0.17's register_api_tokens and ApiTokenViews, ui v0.19's API tokens section):
a user creates one at /settings, a script uses it as `Authorization: Bearer`,
and revoking it refuses the next call."""

import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

from .conftest import web_login

HX = {"HX-Request": "true"}
HTML = {"Accept": "text/html"}
ROOT = Path(__file__).resolve().parents[1]


async def _create(client, name="backup script", expiry="90"):
    resp = await client.post("/settings/api-tokens", headers=HX,
                             data={"name": name, "expires_in_days": expiry})
    assert resp.status_code == 200, resp.text
    plaintext = re.search(r'id="gth-settings-api_tokens-new-token" value="([^"]+)"', resp.text).group(1)
    token_id = re.search(r'hx-delete="/settings/api-tokens/([0-9a-f]{32})"', resp.text).group(1)
    return plaintext, token_id


async def test_a_script_authenticates_with_a_token_until_it_is_revoked(gth_client):
    await web_login(gth_client, "pat-user")
    page = await gth_client.get("/settings", headers=HTML)
    assert 'id="gth-settings-api_tokens"' in page.text

    plaintext, token_id = await _create(gth_client)
    bearer = {"Authorization": f"Bearer {plaintext}"}
    assert (await gth_client.get("/api/transactions/", headers=bearer)).status_code == 200

    revoked = await gth_client.delete(f"/settings/api-tokens/{token_id}", headers=HX)
    assert revoked.status_code == 200
    assert (await gth_client.get("/api/transactions/", headers=bearer)).status_code == 401


async def test_the_plaintext_is_shown_once(gth_client):
    await web_login(gth_client, "pat-once")
    plaintext, _ = await _create(gth_client)
    assert plaintext not in (await gth_client.get("/settings", headers=HTML)).text


async def test_a_token_cant_create_tokens(gth_client):
    await web_login(gth_client, "pat-self")
    plaintext, _ = await _create(gth_client)
    resp = await gth_client.post("/settings/api-tokens", headers={**HX, "Authorization": f"Bearer {plaintext}"},
                                 data={"name": "more", "expires_in_days": "90"})
    assert resp.status_code == 403


def test_migration_creates_and_drops_gth_api_tokens(tmp_path):
    db = tmp_path / "migrate.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db}", "ASYNC_DATABASE_URL": f"sqlite+aiosqlite:///{db}"}

    def alembic(*args):
        # A subprocess, as in test_web_audit: env.py imports the models afresh.
        subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, check=True,
                       capture_output=True)

    def tables():
        with sqlite3.connect(db) as conn:
            return {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}

    alembic("upgrade", "head")
    with sqlite3.connect(db) as conn:
        cols = [r[1] for r in conn.execute("pragma table_info(gth_api_tokens)")]
    # greentechhub_core.sqlalchemy.api_tokens_table's columns, in order.
    assert cols == ["id", "token_hash", "owner", "name", "scopes", "created_at", "expires_at", "last_used_at"]
    alembic("downgrade", "7c02b9a0cfe8")  # back to before gth_api_tokens
    assert "gth_api_tokens" not in tables() and "gth_audit_log" in tables()
