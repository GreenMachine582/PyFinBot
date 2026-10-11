"""The audit log (greentechhub-fastapi v0.16's register_audit, on core's
gth_audit_log): fastapi's views record sign-ins and the like by themselves;
PyFinBot's syncs and imports add theirs (core/audit_events.py), from the web
and the API alike; admins read it at /admin/audit."""
import io
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from pyfinbot.pyfinbot import AUDIT_STORE

from .conftest import create_stock, make_admin, register_and_login, web_login

HX = {"HX-Request": "true"}
HTML = {"Accept": "text/html"}
ROOT = Path(__file__).resolve().parents[1]
CSV = "date,stock,type,units,price,fees,notes\n2024-08-01,ASX:AUD,Buy,10,20,0,\n2024-08-02,ASX:NOPE,Buy,1,1,0,\n"


@pytest.fixture
def recorded():
    """The entries recorded during the test, newest last. Read off the store's
    record() rather than back from the table: in tests every session shares
    one connection, so a route session's closing rollback can undo an entry
    the store committed inside it (in production each has its own)."""
    with patch.object(AUDIT_STORE, "record", wraps=AUDIT_STORE.record) as record:
        def entries(action: str, actor: str | None = None):
            found = [c.args[0] for c in record.call_args_list
                     if c.args[0].action == action and (actor is None or c.args[0].actor == actor)]
            assert found, f"no {action} entry"
            return found[-1]
        yield entries


async def test_a_web_sign_in_is_recorded(gth_client, recorded):
    await web_login(gth_client, "audit-signin")
    assert (recorded("auth.signed_in", "audit-signin")).actor == "audit-signin"


async def test_a_web_import_is_recorded(gth_client, recorded):
    await web_login(gth_client, "audit-import")
    await create_stock(gth_client, "AUD", "ASX", "Audit Co")
    resp = await gth_client.post("/import", headers=HX, files={"file": ("t.csv", io.BytesIO(CSV.encode()), "text/csv")})
    assert resp.status_code == 200, resp.text
    entry = recorded("transactions.imported", "audit-import")
    assert entry.summary == "Imported 1 of 2 rows from t.csv"
    assert entry.details == {"filename": "t.csv", "total_rows": 2, "created": 1, "skipped": 1, "row_errors": 1}


async def test_an_api_import_is_recorded_against_the_token(gth_client, recorded):
    headers = await register_and_login(gth_client, "audit-api")
    await create_stock(gth_client, "AUD", "ASX", "Audit Co")
    resp = await gth_client.post("/api/transactions/import", headers=headers,
                                 files={"file": ("api.csv", io.BytesIO(CSV.encode()), "text/csv")})
    assert resp.status_code == 200, resp.text
    assert (recorded("transactions.imported", "audit-api")).details["filename"] == "api.csv"


async def test_an_email_sync_is_recorded(gth_client, recorded):
    await web_login(gth_client, "audit-email")
    summary = SimpleNamespace(total_emails=3, created=2, skipped=1, errors=["one bad email"])
    with patch("pyfinbot.web.routes.emails.load_email_account", new=AsyncMock()), \
            patch("pyfinbot.web.routes.emails.sync_commsec_emails", new=AsyncMock(return_value=summary)):
        resp = await gth_client.post("/emails/sync", headers=HX)
    assert resp.status_code == 200, resp.text
    entry = recorded("emails.synced", "audit-email")
    assert entry.details == {"total_emails": 3, "created": 2, "skipped": 1, "errors": 1}


async def test_a_dividend_sync_of_one_stock_targets_it(gth_client, recorded):
    await web_login(gth_client, "audit-div")
    stock = await create_stock(gth_client, "DIV", "ASX", "Div Co")
    with patch("pyfinbot.web.routes.dividends.syncDividends", new=AsyncMock(return_value=([1], [], []))):
        resp = await gth_client.post("/dividends/sync", headers=HX, data={"stock_id": str(stock["id"])})
    assert resp.status_code == 200, resp.text
    entry = recorded("dividends.synced", "audit-div")
    assert (entry.target_type, entry.target_id, entry.details["created"]) == ("stock", str(stock["id"]), 1)


async def test_a_market_sync_is_recorded(gth_client, recorded):
    await web_login(gth_client, "audit-market")
    with patch("pyfinbot.web.routes.stocks.syncMarket", new=AsyncMock(return_value=([1, 2], [3], []))):
        resp = await gth_client.post("/stocks/sync/asx", headers=HX)
    assert resp.status_code == 204, resp.text  # a toast only
    entry = recorded("stocks.market_synced", "audit-market")
    assert (entry.target_type, entry.target_id) == ("market", "ASX") and entry.summary == "ASX: 2 created, 1 updated, 0 archived"


async def test_the_audit_page_is_for_admins(gth_client):
    assert (await gth_client.get("/admin/audit", follow_redirects=False)).status_code == 303
    await web_login(gth_client, "audit-nobody")
    assert (await gth_client.get("/admin/audit")).status_code == 403
    assert 'href="/admin/audit"' not in (await gth_client.get("/", headers=HTML)).text
    await web_login(gth_client, "audit-admin")
    await make_admin(gth_client, "audit-admin")
    page = await gth_client.get("/admin/audit")
    assert page.status_code == 200 and "auth.signed_in" in page.text and "audit-admin" in page.text
    assert 'href="/admin/audit"' in (await gth_client.get("/", headers=HTML)).text


def test_migration_creates_and_drops_gth_audit_log(tmp_path):
    db = tmp_path / "migrate.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db}", "ASYNC_DATABASE_URL": f"sqlite+aiosqlite:///{db}"}

    def alembic(*args):
        # A subprocess, as in test_web_login_throttle: env.py imports the models afresh.
        subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, check=True,
                       capture_output=True)

    def tables():
        with sqlite3.connect(db) as conn:
            return {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}

    alembic("upgrade", "head")
    with sqlite3.connect(db) as conn:
        cols = [r[1] for r in conn.execute("pragma table_info(gth_audit_log)")]
    assert cols == ["id", "at", "actor", "action", "target_type", "target_id", "summary", "details"]
    alembic("downgrade", "e8a3c6d1f204")  # back to before gth_audit_log
    assert "gth_audit_log" not in tables() and "gth_login_attempts" in tables()
