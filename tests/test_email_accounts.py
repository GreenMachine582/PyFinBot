"""Per-user email accounts for Commsec sync (greentechhub v0.12 adoption,
item 4): each user's mailbox comes from their own settings, the app password
a write-only, encrypted greentechhub secret setting."""
import importlib
import warnings
from unittest.mock import patch

import pytest
from greentechhub_core.settings.crypto import FernetCipher
from sqlalchemy import select

from pyfinbot.core.email_accounts import load_email_account
from pyfinbot.core.email_sync import EmailAccount
from pyfinbot.core.market_sync import sync_guard
from pyfinbot.models.settings_models import SETTINGS_TABLE
from pyfinbot.web.routes.emails import email_sync_lock

from .conftest import create_stock, hx_triggers, register_and_login, web_login
from .test_email_sync import _fake_messages

HX = {"HX-Request": "true"}
FETCH = "pyfinbot.core.commsec_import.fetch_commsec_emails"
MARK = "pyfinbot.core.commsec_import.mark_seen"
PASSWORD = "abcd efgh ijkl mnop"
settings_module = importlib.import_module("pyfinbot.core.settings")


def _service():
    from greentechhub_fastapi.settings import get_settings_config

    from pyfinbot.pyfinbot import app

    return get_settings_config(app).settings


async def _save_account(client, address, password=PASSWORD, **extra):
    resp = await client.post("/settings/preferences", headers=HX, data={
        "email.address": address, "email.app_password": password, **extra})
    assert resp.status_code == 200, resp.text
    return resp


async def test_settings_page_has_a_write_only_password(client):
    await web_login(client, "acct-form")
    await _save_account(client, "form@example.com")
    page = (await client.get("/settings", headers={"Accept": "text/html"})).text
    assert "Email sync" in page and 'value="form@example.com"' in page
    assert 'type="password"' in page and "Saved. Leave blank to keep it." in page
    assert PASSWORD not in page


async def test_password_is_encrypted_at_rest_and_never_rendered(client, connection):
    await web_login(client, "acct-crypt")
    await _save_account(client, "crypt@example.com")
    rows = (await connection.execute(select(SETTINGS_TABLE.c.key, SETTINGS_TABLE.c.value).where(
        SETTINGS_TABLE.c.subject == "acct-crypt"))).all()
    stored = dict(rows)["email.app_password"]
    assert PASSWORD not in stored and stored.startswith("gAAAA")  # a Fernet token
    for path in ("/settings", "/emails", "/"):
        assert PASSWORD not in (await client.get(path, headers={"Accept": "text/html"})).text, path


async def test_blank_keeps_and_clear_removes_the_password(client):
    await web_login(client, "acct-keep")
    await _save_account(client, "keep@example.com")
    await _save_account(client, "keep@example.com", password="")  # the form re-posted, field blank
    account = await load_email_account(_service(), "acct-keep")
    assert account.imap is not None and account.imap.password == PASSWORD

    await client.post("/settings/preferences", headers=HX, data={
        "email.address": "keep@example.com", "email.app_password": "",
        "email.app_password.__clear": "true"})
    account = await load_email_account(_service(), "acct-keep")
    assert account.imap is None and not account.configured
    assert "isn't set up yet" in (await client.get("/emails")).text


async def test_each_user_syncs_only_their_own_mailbox(client):
    used: list[EmailAccount] = []

    def fake_fetch(account, *, only_unseen=True):
        used.append(account)
        return _fake_messages("bought_rmd.txt") if account.imap.username == "alice@example.com" else []

    await web_login(client, "acct-alice")
    await create_stock(client, "RMD", name="ResMed Inc")
    await _save_account(client, "alice@example.com", "alice-app-pw", **{"email.imap_port": "993"})
    with patch(FETCH, side_effect=fake_fetch), patch(MARK) as mark:
        assert "1 imported" in (await client.post("/emails/sync", headers=HX)).text
    assert (used[-1].imap.username, used[-1].imap.password) == ("alice@example.com", "alice-app-pw")
    assert mark.call_args.args[0].imap.username == "alice@example.com"

    await web_login(client, "acct-bob")
    await _save_account(client, "bob@example.com", "bob-app-pw", **{"email.mailbox": "Commsec"})
    with patch(FETCH, side_effect=fake_fetch), patch(MARK):
        resp = await client.post("/emails/sync", headers=HX)
    assert hx_triggers(resp)["showToast"]["message"] == "No new Commsec emails."
    bob = used[-1].imap
    assert (bob.username, bob.password, bob.mailbox) == ("bob@example.com", "bob-app-pw", "Commsec")
    assert "RMD" not in (await client.get("/transactions")).text  # alice's import isn't bob's


async def test_not_configured_sync_and_api(client):
    await web_login(client, "acct-none")
    resp = await client.post("/emails/sync", headers=HX)  # real fetch: no account, no IMAP
    assert resp.status_code == 422
    assert "Set your email address and app password in Settings" in resp.text
    assert 'href="/settings#gth-settings-preferences"' in resp.text

    headers = await register_and_login(client, "acct-api")
    api = await client.post("/api/emails/sync-commsec", headers=headers)
    assert api.status_code == 503 and "Settings" in api.json()["message"]
    assert api.json()["code"] == "email_sync_failed"


async def test_an_unreadable_password_asks_for_it_again(client):
    await web_login(client, "acct-rekey")
    await _save_account(client, "rekey@example.com")
    service = _service()
    with patch.object(service, "_cipher", FernetCipher(FernetCipher.generate_key())):
        resp = await client.post("/emails/sync", headers=HX)
        assert resp.status_code == 422 and "Enter it again in Settings" in resp.text
        page = (await client.get("/emails")).text
    assert "Enter it again in Settings" in page


async def test_sync_locks_are_per_user(client):
    await web_login(client, "acct-lock-b")
    with sync_guard(email_sync_lock("acct-lock-a")) as held, patch(FETCH, return_value=[]), patch(MARK):
        assert held  # user A's sync is running
        resp = await client.post("/emails/sync", headers=HX)
    assert hx_triggers(resp)["showToast"]["kind"] == "info"  # user B still synced
    assert email_sync_lock("a") != email_sync_lock("b") and "/" not in email_sync_lock("x/y")


def test_retired_settings_warn_and_still_load(monkeypatch):
    with pytest.warns(UserWarning, match="GMAIL_ADDRESS is no longer used"):
        assert settings_module._warn_retired({"GMAIL_ADDRESS": "old@example.com"}) == ["GMAIL_ADDRESS"]
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert settings_module._warn_retired({}) == []
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "x")
    assert settings_module.Settings(secret_key="k").environment  # extra env keys are ignored
