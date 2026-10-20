"""In-app notices for syncs and imports (greentechhub-fastapi's
register_notifications and notify): each completed run leaves one for the user
who ran it, behind the navbar bell and at /notifications, toned by how it went.
A notice never fails the run, and gth_notifications is migrated."""
import io
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from .conftest import create_stock, web_login

HX = {"HX-Request": "true"}
HTML = {"Accept": "text/html"}
CSV = "date,stock,type,units,price,fees,notes\n2024-08-01,ASX:NTC,Buy,10,20,0,\n2024-08-02,ASX:NOPE,Buy,1,1,0,\n"


async def _unread(client) -> int:
    badge = (await client.get("/notifications/badge", headers=HX)).text
    found = re.search(r">\s*(\d+)\s*<", badge)
    return int(found.group(1)) if found else 0


async def _notices(client) -> str:
    return (await client.get("/notifications", headers=HTML)).text


async def test_an_email_sync_leaves_a_notice_for_its_user_only(gth_client):
    await web_login(gth_client, "notice-email")
    summary = SimpleNamespace(total_emails=3, created=2, skipped=1, errors=[])
    with patch("pyfinbot.web.routes.emails.load_email_account", new=AsyncMock()), \
            patch("pyfinbot.web.routes.emails.sync_commsec_emails", new=AsyncMock(return_value=summary)):
        assert (await gth_client.post("/emails/sync", headers=HX)).status_code == 200
    assert await _unread(gth_client) == 1
    page = await _notices(gth_client)
    assert "Email sync finished" in page and "Imported 2 of 3 emails" in page
    assert "gth-notification-success" in page

    await web_login(gth_client, "notice-other")
    assert await _unread(gth_client) == 0


async def test_a_partial_import_is_a_warning(gth_client):
    await web_login(gth_client, "notice-import")
    await create_stock(gth_client, "NTC", "ASX", "Notice Co")
    resp = await gth_client.post("/import", headers=HX,
                                 files={"file": ("t.csv", io.BytesIO(CSV.encode()), "text/csv")})
    assert resp.status_code == 200, resp.text
    page = await _notices(gth_client)
    assert "Import finished" in page and "Imported 1 of 2 rows from t.csv" in page
    assert "gth-notification-warning" in page


async def test_a_failed_dividend_sync_is_danger(gth_client):
    await web_login(gth_client, "notice-div")
    stock = await create_stock(gth_client, "DVN", "ASX", "Div Notice Co")
    with patch("pyfinbot.web.routes.dividends.syncDividends",
               new=AsyncMock(return_value=([], [], ["ASX:DVN: no data"]))):
        assert (await gth_client.post("/dividends/sync", headers=HX,
                                      data={"stock_id": str(stock["id"])})).status_code == 200
    page = await _notices(gth_client)
    assert "Dividend sync finished" in page and "gth-notification-danger" in page


async def test_a_market_sync_notifies_whoever_ran_it(gth_client):
    await web_login(gth_client, "notice-market")
    with patch("pyfinbot.web.routes.stocks.syncMarket", new=AsyncMock(return_value=([1, 2], [3], []))):
        assert (await gth_client.post("/stocks/sync/asx", headers=HX)).status_code == 204
    page = await _notices(gth_client)
    assert "ASX sync finished" in page and "ASX: 2 created, 1 updated, 0 archived" in page


async def test_a_notice_failure_never_fails_the_sync(gth_client):
    await web_login(gth_client, "notice-broken")
    with patch("pyfinbot.core.audit_events.notify", new=AsyncMock(side_effect=RuntimeError("store down"))), \
            patch("pyfinbot.web.routes.stocks.syncMarket", new=AsyncMock(return_value=([], [], []))):
        assert (await gth_client.post("/stocks/sync/asx", headers=HX)).status_code == 204
    assert await _unread(gth_client) == 0
