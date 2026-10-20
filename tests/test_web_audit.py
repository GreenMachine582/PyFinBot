"""The audit log (greentechhub-fastapi v0.16's register_audit, on core's
gth_audit_log): fastapi's views record sign-ins and the like by themselves;
PyFinBot's syncs and imports add theirs (core/audit_events.py), from the web
and the API alike; admins read it at /admin/audit."""
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from pyfinbot.pyfinbot import AUDIT_STORE

from .conftest import create_stock, make_admin, register_and_login, user_id, web_login

HX = {"HX-Request": "true"}
HTML = {"Accept": "text/html"}
CSV = "date,stock,type,units,price,fees,notes\n2024-08-01,ASX:AUD,Buy,10,20,0,\n2024-08-02,ASX:NOPE,Buy,1,1,0,\n"


@pytest.fixture
def recorded():
    """The newest entry for an action (and actor, by username), read back
    from gth_audit_log through the store. Since greentechhub-core v0.15 the test sessions release
    a read-only SAVEPOINT on close, so a route session that stays open around
    the store's own write no longer undoes it."""
    async def entry(action: str, actor: str | None = None):
        actor_id = await user_id(actor) if actor is not None else None
        found = await AUDIT_STORE.entries(action=action, actor=actor_id, limit=1)
        assert found, f"no {action} entry in gth_audit_log"
        return found[0]
    return entry


async def test_a_web_sign_in_is_recorded(gth_client, recorded):
    await web_login(gth_client, "audit-signin")
    assert (await recorded("auth.signed_in", "audit-signin")).actor == await user_id("audit-signin")


async def test_a_web_import_is_recorded(gth_client, recorded):
    await web_login(gth_client, "audit-import")
    await create_stock(gth_client, "AUD", "ASX", "Audit Co")
    resp = await gth_client.post("/import", headers=HX, files={"file": ("t.csv", io.BytesIO(CSV.encode()), "text/csv")})
    assert resp.status_code == 200, resp.text
    entry = await recorded("transactions.imported", "audit-import")
    assert entry.summary == "Imported 1 of 2 rows from t.csv"
    assert entry.details == {"filename": "t.csv", "total_rows": 2, "created": 1, "skipped": 1, "row_errors": 1}


async def test_an_api_import_is_recorded_against_the_token(gth_client, recorded):
    headers = await register_and_login(gth_client, "audit-api")
    await create_stock(gth_client, "AUD", "ASX", "Audit Co")
    resp = await gth_client.post("/api/transactions/import", headers=headers,
                                 files={"file": ("api.csv", io.BytesIO(CSV.encode()), "text/csv")})
    assert resp.status_code == 200, resp.text
    assert (await recorded("transactions.imported", "audit-api")).details["filename"] == "api.csv"


async def test_an_email_sync_is_recorded(gth_client, recorded):
    await web_login(gth_client, "audit-email")
    summary = SimpleNamespace(total_emails=3, created=2, skipped=1, errors=["one bad email"])
    with patch("pyfinbot.web.routes.emails.load_email_account", new=AsyncMock()), \
            patch("pyfinbot.web.routes.emails.sync_commsec_emails", new=AsyncMock(return_value=summary)):
        resp = await gth_client.post("/emails/sync", headers=HX)
    assert resp.status_code == 200, resp.text
    entry = await recorded("emails.synced", "audit-email")
    assert entry.details == {"total_emails": 3, "created": 2, "skipped": 1, "errors": 1}


async def test_a_dividend_sync_of_one_stock_targets_it(gth_client, recorded):
    await web_login(gth_client, "audit-div")
    stock = await create_stock(gth_client, "DIV", "ASX", "Div Co")
    with patch("pyfinbot.web.routes.dividends.syncDividends", new=AsyncMock(return_value=([1], [], []))):
        resp = await gth_client.post("/dividends/sync", headers=HX, data={"stock_id": str(stock["id"])})
    assert resp.status_code == 200, resp.text
    entry = await recorded("dividends.synced", "audit-div")
    assert (entry.target_type, entry.target_id, entry.details["created"]) == ("stock", str(stock["id"]), 1)


async def test_a_market_sync_is_recorded(gth_client, recorded):
    await web_login(gth_client, "audit-market")
    with patch("pyfinbot.web.routes.stocks.syncMarket", new=AsyncMock(return_value=([1, 2], [3], []))):
        resp = await gth_client.post("/stocks/sync/asx", headers=HX)
    assert resp.status_code == 204, resp.text  # a toast only
    entry = await recorded("stocks.market_synced", "audit-market")
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
