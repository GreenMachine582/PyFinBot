"""Leaner routes on the gth helpers (core v0.15+, fastapi v0.18, ui v0.20):
stocks and transactions load through fastapi's get_owned_or_404 (transactions
with their stock eager-loaded through options=), counts read through ui's
pluralise, the sync locks are core's held_lock with lock_name for per-user
names, and retired settings warn through core's GTHBaseSettings.retired."""

import importlib
import re
import warnings

import pytest
from greentechhub_core.background import lock_name

from pyfinbot.web.routes.emails import EMAIL_SYNC_LOCK

from .conftest import create_stock, web_login

settings_module = importlib.import_module("pyfinbot.core.settings")


async def test_a_missing_stock_is_a_404(gth_client):
    await web_login(gth_client, "lean-stocks")
    stock = await create_stock(gth_client, symbol="LEAN")
    assert (await gth_client.get(f"/stocks/{stock['id']}/edit")).status_code == 200
    missing = await gth_client.get("/stocks/999999/edit")
    assert missing.status_code == 404 and "Stock not found" in missing.text


async def test_a_missing_transaction_is_a_404(gth_client):
    await web_login(gth_client, "lean-transactions")
    for resp in (await gth_client.get("/transactions/999999/edit"),
                 await gth_client.get("/transactions/999999/delete"),
                 await gth_client.delete("/transactions/999999")):
        assert resp.status_code == 404 and "Transaction not found" in resp.text


def test_email_sync_lock_names_are_per_user_and_filename_safe():
    alice, bob = lock_name(EMAIL_SYNC_LOCK, "alice"), lock_name(EMAIL_SYNC_LOCK, "bob")
    assert alice != bob and alice == lock_name(EMAIL_SYNC_LOCK, "alice")
    assert re.fullmatch(r"commsec-email-sync-[0-9a-f]{16}", lock_name(EMAIL_SYNC_LOCK, "../x y"))


def test_retired_settings_warn_once_per_reason_through_core(monkeypatch):
    for name in settings_module.Settings.retired:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GMAIL_ADDRESS", "old@example.com")
    monkeypatch.setenv("GMAIL_MAILBOX", "INBOX")
    with pytest.warns(UserWarning) as record:
        settings_module.Settings(secret_key="k", _env_file=None)
    retired = [str(w.message) for w in record if "no longer used" in str(w.message)]
    assert retired == ["GMAIL_ADDRESS, GMAIL_MAILBOX are no longer used: each user sets their own email "
                       "account at /settings › Email sync. Remove them from the environment/.env."]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert not hasattr(settings_module, "_warn_retired")
