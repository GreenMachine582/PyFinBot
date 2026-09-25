"""Integration tests for the /emails web page (IMAP mocked, fixtures shared
with test_email_sync.py)."""
from unittest.mock import patch

from pyfinbot.core.email_sync import GmailNotConfiguredError
from pyfinbot.core.market_sync import sync_guard
from pyfinbot.web.routes.emails import LOCK

from .conftest import create_stock, hx_triggers, web_login
from .test_email_sync import _fake_messages

HX = {"HX-Request": "true"}
FETCH = "pyfinbot.core.commsec_import.fetch_commsec_emails"
MARK = "pyfinbot.core.commsec_import.mark_seen"


class TestAuthGuard:
    async def test_page_redirects_to_login(self, client):
        resp = await client.get("/emails", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/login"

    async def test_htmx_sync_gets_hx_redirect(self, client):
        resp = await client.post("/emails/sync", headers=HX, follow_redirects=False)
        assert resp.status_code == 401
        assert resp.headers["HX-Redirect"] == "/login"


class TestPage:
    async def test_renders_sync_button(self, client):
        await web_login(client, "web-emails")
        resp = await client.get("/emails")
        assert resp.status_code == 200
        assert 'hx-post="/emails/sync"' in resp.text
        assert 'href="/emails" aria-current="page"' in resp.text  # navbar marks the active page

    async def test_not_configured_hint(self, client):
        await web_login(client, "web-emails")
        with patch("pyfinbot.web.routes.emails.settings.GMAIL_ADDRESS", ""):
            resp = await client.get("/emails")
        assert "Gmail isn't configured yet" in resp.text

    async def test_no_hint_when_configured(self, client):
        await web_login(client, "web-emails")
        with patch("pyfinbot.web.routes.emails.settings.GMAIL_ADDRESS", "me@example.com"), \
                patch("pyfinbot.web.routes.emails.settings.GMAIL_APP_PASSWORD", "app-password"):
            resp = await client.get("/emails")
        assert "configured yet" not in resp.text


class TestSync:
    async def test_imports_emails(self, client):
        await web_login(client, "web-emails")
        await create_stock(client, "RMD", name="ResMed Inc")
        await create_stock(client, "WOW", name="Woolworths Group")
        with patch(FETCH, return_value=_fake_messages("bought_rmd.txt", "sold_wow.txt")), \
                patch(MARK) as mock_mark:
            resp = await client.post("/emails/sync", headers=HX)
        assert resp.status_code == 200
        assert "<html" not in resp.text  # the result fragment only
        assert "2 emails" in resp.text and "2 imported" in resp.text
        assert 'href="/transactions"' in resp.text
        triggers = hx_triggers(resp)
        assert triggers["showToast"]["kind"] == "success"
        assert triggers["showToast"]["message"] == "Imported 2 transactions."
        assert triggers["transactionsChanged"]
        mock_mark.assert_called_once()

        page = await client.get("/transactions")
        assert "RMD" in page.text and "WOW" in page.text  # booked to the web user

    async def test_skipped_emails_are_listed(self, client):
        await web_login(client, "web-emails")
        await create_stock(client, "RMD", name="ResMed Inc")  # WOW isn't tracked
        with patch(FETCH, return_value=_fake_messages("bought_rmd.txt", "sold_wow.txt")), patch(MARK):
            resp = await client.post("/emails/sync")
        assert "1 imported" in resp.text and "1 skipped" in resp.text
        assert "Stock &#39;ASX:WOW&#39; not found" in resp.text
        triggers = hx_triggers(resp)
        assert triggers["showToast"]["kind"] == "warning"
        assert triggers["showToast"]["message"] == "Imported 1 transaction; 1 skipped."

    async def test_no_new_emails(self, client):
        await web_login(client, "web-emails")
        with patch(FETCH, return_value=[]), patch(MARK):
            resp = await client.post("/emails/sync")
        triggers = hx_triggers(resp)
        assert triggers["showToast"]["kind"] == "info"
        assert "transactionsChanged" not in triggers
        assert 'href="/transactions"' not in resp.text

    async def test_not_configured(self, client):
        await web_login(client, "web-emails")
        with patch(FETCH, side_effect=GmailNotConfiguredError("GMAIL_ADDRESS/GMAIL_APP_PASSWORD not configured")):
            resp = await client.post("/emails/sync")
        assert resp.status_code == 422
        assert "not configured" in resp.text
        assert hx_triggers(resp)["showToast"]["kind"] == "danger"

    async def test_imap_failure(self, client):
        await web_login(client, "web-emails")
        with patch(FETCH, side_effect=RuntimeError("connection refused")):
            resp = await client.post("/emails/sync")
        assert resp.status_code == 422
        assert "IMAP fetch failed: connection refused" in resp.text

    async def test_refused_while_running(self, client):
        await web_login(client, "web-emails")
        with sync_guard(LOCK) as held, patch(FETCH) as mock_fetch:
            assert held
            resp = await client.post("/emails/sync")
        assert resp.status_code == 204
        assert hx_triggers(resp)["showToast"]["kind"] == "warning"
        mock_fetch.assert_not_called()
