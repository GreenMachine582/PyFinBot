"""Integration tests for the /emails web page (IMAP mocked, fixtures shared
with test_email_sync.py)."""
from unittest.mock import patch

from pyfinbot.core.email_sync import NOT_CONFIGURED, EmailNotConfiguredError
from greentechhub_core.background import held_lock, lock_name

from pyfinbot.core.settings import settings
from pyfinbot.web.routes.emails import EMAIL_SYNC_LOCK

from .conftest import create_stock, hx_triggers, user_id, web_login
from .test_email_sync import _fake_messages

HX = {"HX-Request": "true"}
FETCH = "pyfinbot.core.commsec_import.fetch_commsec_emails"
MARK = "pyfinbot.core.commsec_import.mark_seen"


class TestAuthGuard:
    async def test_page_redirects_to_login(self, gth_client):
        resp = await gth_client.get("/emails", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/login"

    async def test_htmx_sync_gets_hx_redirect(self, gth_client):
        resp = await gth_client.post("/emails/sync", headers=HX, follow_redirects=False)
        assert resp.status_code == 401
        assert resp.headers["HX-Redirect"] == "/login"


class TestPage:
    async def test_renders_sync_button(self, gth_client):
        await web_login(gth_client, "web-emails")
        resp = await gth_client.get("/emails")
        assert resp.status_code == 200
        assert 'hx-post="/emails/sync"' in resp.text
        assert 'href="/emails" aria-current="page"' in resp.text  # navbar marks the active page

    async def test_not_configured_hint(self, gth_client):
        await web_login(gth_client, "web-emails")
        resp = await gth_client.get("/emails")
        assert "Your email account isn't set up yet" in resp.text
        assert 'href="/settings#gth-settings-preferences"' in resp.text

    async def test_no_hint_when_configured(self, gth_client):
        await web_login(gth_client, "web-emails")
        await gth_client.post("/settings/preferences", headers=HX, data={
            "email.address": "me@example.com", "email.app_password": "app-password"})
        resp = await gth_client.get("/emails")
        assert "set up yet" not in resp.text


class TestSync:
    async def test_imports_emails(self, gth_client):
        await web_login(gth_client, "web-emails")
        await create_stock(gth_client, "RMD", name="ResMed Inc")
        await create_stock(gth_client, "WOW", name="Woolworths Group")
        with patch(FETCH, return_value=_fake_messages("bought_rmd.txt", "sold_wow.txt")), \
                patch(MARK) as mock_mark:
            resp = await gth_client.post("/emails/sync", headers=HX)
        assert resp.status_code == 200
        assert "<html" not in resp.text  # the result fragment only
        assert "2 emails" in resp.text and "2 imported" in resp.text
        assert 'href="/transactions"' in resp.text
        triggers = hx_triggers(resp)
        assert triggers["showToast"]["kind"] == "success"
        assert triggers["showToast"]["message"] == "Imported 2 transactions."
        assert triggers["transactionsChanged"]
        mock_mark.assert_called_once()

        page = await gth_client.get("/transactions")
        assert "RMD" in page.text and "WOW" in page.text  # booked to the web user

    async def test_skipped_emails_are_listed(self, gth_client):
        await web_login(gth_client, "web-emails")
        await create_stock(gth_client, "RMD", name="ResMed Inc")
        with patch(FETCH, return_value=_fake_messages("bought_rmd.txt", "bought_rmd.txt")), patch(MARK):
            resp = await gth_client.post("/emails/sync")
        assert "1 imported" in resp.text and "1 skipped" in resp.text
        assert "UID 2: Duplicate transaction" in resp.text
        triggers = hx_triggers(resp)
        assert triggers["showToast"]["kind"] == "warning"
        assert triggers["showToast"]["message"] == "Imported 1 transaction; 1 skipped."

    async def test_no_new_emails(self, gth_client):
        await web_login(gth_client, "web-emails")
        with patch(FETCH, return_value=[]), patch(MARK):
            resp = await gth_client.post("/emails/sync")
        triggers = hx_triggers(resp)
        assert triggers["showToast"]["kind"] == "info"
        assert "transactionsChanged" not in triggers
        assert 'href="/transactions"' not in resp.text

    async def test_not_configured(self, gth_client):
        await web_login(gth_client, "web-emails")
        with patch(FETCH, side_effect=EmailNotConfiguredError(NOT_CONFIGURED)):
            resp = await gth_client.post("/emails/sync")
        assert resp.status_code == 422
        assert "Set your email address and app password in Settings" in resp.text
        assert 'href="/settings#gth-settings-preferences"' in resp.text
        assert hx_triggers(resp)["showToast"]["kind"] == "danger"

    async def test_imap_failure(self, gth_client):
        await web_login(gth_client, "web-emails")
        with patch(FETCH, side_effect=RuntimeError("connection refused")):
            resp = await gth_client.post("/emails/sync")
        assert resp.status_code == 422
        assert "IMAP fetch failed: connection refused" in resp.text

    async def test_refused_while_running(self, gth_client):
        await web_login(gth_client, "web-emails")
        with (held_lock(settings, lock_name(EMAIL_SYNC_LOCK, await user_id("web-emails")), ttl=60) as held,
              patch(FETCH) as mock_fetch):
            assert held
            resp = await gth_client.post("/emails/sync")
        assert resp.status_code == 204
        assert hx_triggers(resp)["showToast"]["kind"] == "warning"
        mock_fetch.assert_not_called()
