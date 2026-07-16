"""Integration tests for POST /api/emails/sync-commsec (IMAP mocked — no real
network/mailbox access; fixtures are built from real Commsec confirmation
email samples)."""
import email
from pathlib import Path
from unittest.mock import patch

from pyfinbot.core.email_sync import GmailNotConfiguredError

from .conftest import register_and_login

USER_ID = "email-user"
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "commsec_emails"


def _load_fixture(name: str) -> email.message.Message:
    text = (FIXTURES_DIR / name).read_text(encoding="utf-8")
    return email.message_from_string(text)


def _fake_messages(*names: str):
    return [(f"{i}".encode(), _load_fixture(name)) for i, name in enumerate(names, start=1)]


async def _create_stock(client, symbol, market="ASX", name="Test Co"):
    resp = await client.post("/api/stocks/", json={"symbol": symbol, "market": market, "name": name})
    assert resp.status_code == 201
    return resp.json()


class TestSyncCommsecEmails:
    async def test_no_token_returns_401(self, client):
        resp = await client.post("/api/emails/sync-commsec")
        assert resp.status_code == 401

    async def test_no_credentials_returns_503(self, client):
        headers = await register_and_login(client, USER_ID)
        with patch(
            "pyfinbot.api.email_routes.fetch_commsec_emails",
            side_effect=GmailNotConfiguredError("GMAIL_ADDRESS/GMAIL_APP_PASSWORD not configured"),
        ):
            resp = await client.post("/api/emails/sync-commsec", headers=headers)
        assert resp.status_code == 503

    async def test_imap_failure_returns_502(self, client):
        headers = await register_and_login(client, USER_ID)
        with patch("pyfinbot.api.email_routes.fetch_commsec_emails", side_effect=RuntimeError("connection refused")):
            resp = await client.post("/api/emails/sync-commsec", headers=headers)
        assert resp.status_code == 502

    async def test_creates_transaction_from_bought_email(self, client):
        headers = await register_and_login(client, USER_ID)
        await _create_stock(client, "RMD", name="ResMed Inc")

        with patch(
            "pyfinbot.api.email_routes.fetch_commsec_emails",
            return_value=_fake_messages("bought_rmd.txt"),
        ), patch("pyfinbot.api.email_routes.mark_seen") as mock_mark_seen:
            resp = await client.post("/api/emails/sync-commsec", headers=headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_emails"] == 1
        assert data["created"] == 1
        assert data["skipped"] == 0
        mock_mark_seen.assert_called_once()

        txns = await client.get("/api/transactions/", headers=headers)
        items = txns.json()["items"]
        assert len(items) == 1
        assert items[0]["type"] == "Buy"
        assert float(items[0]["units"]) == 50
        assert float(items[0]["price"]) == 29.80
        assert float(items[0]["fees"]) == 10.00
        assert items[0]["transaction_date"] == "2026-07-10"

    async def test_creates_transaction_from_sold_email(self, client):
        headers = await register_and_login(client, USER_ID)
        await _create_stock(client, "WOW", name="Woolworths Group")

        with patch(
            "pyfinbot.api.email_routes.fetch_commsec_emails",
            return_value=_fake_messages("sold_wow.txt"),
        ), patch("pyfinbot.api.email_routes.mark_seen"):
            resp = await client.post("/api/emails/sync-commsec", headers=headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 1

        txns = await client.get("/api/transactions/", headers=headers)
        items = txns.json()["items"]
        assert items[0]["type"] == "Sell"
        assert float(items[0]["units"]) == 579

    async def test_unknown_stock_reported_as_error(self, client):
        headers = await register_and_login(client, USER_ID)
        # RMD is never registered as a Stock

        with patch(
            "pyfinbot.api.email_routes.fetch_commsec_emails",
            return_value=_fake_messages("bought_rmd.txt"),
        ), patch("pyfinbot.api.email_routes.mark_seen") as mock_mark_seen:
            resp = await client.post("/api/emails/sync-commsec", headers=headers)

        data = resp.json()
        assert data["created"] == 0
        assert data["skipped"] == 1
        assert len(data["errors"]) == 1
        mock_mark_seen.assert_not_called()

    async def test_duplicate_email_skipped_on_resync(self, client):
        headers = await register_and_login(client, USER_ID)
        await _create_stock(client, "RMD", name="ResMed Inc")

        with patch(
            "pyfinbot.api.email_routes.fetch_commsec_emails",
            return_value=_fake_messages("bought_rmd.txt"),
        ), patch("pyfinbot.api.email_routes.mark_seen"):
            first = await client.post("/api/emails/sync-commsec", headers=headers)
        assert first.json()["created"] == 1

        # Same email processed again (e.g. via ?include_seen=true) should dedupe, not double-book
        with patch(
            "pyfinbot.api.email_routes.fetch_commsec_emails",
            return_value=_fake_messages("bought_rmd.txt"),
        ), patch("pyfinbot.api.email_routes.mark_seen"):
            second = await client.post(
                "/api/emails/sync-commsec", params={"include_seen": True}, headers=headers
            )
        data = second.json()
        assert data["created"] == 0
        assert data["skipped"] == 1

    async def test_unparseable_email_reported_as_error(self, client):
        headers = await register_and_login(client, USER_ID)

        garbage = email.message_from_string(
            "From: bounceback@commsec.com.au\n"
            "Subject: CommSec - Your monthly statement\n"
            "Date: Fri, 10 Jul 2026 09:31:00 +1000\n"
            "Content-Type: text/plain; charset=\"UTF-8\"\n\n"
            "Please find your monthly statement attached.\n"
        )

        with patch(
            "pyfinbot.api.email_routes.fetch_commsec_emails",
            return_value=[(b"1", garbage)],
        ), patch("pyfinbot.api.email_routes.mark_seen") as mock_mark_seen:
            resp = await client.post("/api/emails/sync-commsec", headers=headers)

        data = resp.json()
        assert data["created"] == 0
        assert data["skipped"] == 1
        assert "parse error" in data["errors"][0]
        mock_mark_seen.assert_not_called()
