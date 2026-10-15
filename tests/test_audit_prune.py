"""Audit log retention: on startup, prune_audit_log deletes gth_audit_log
entries older than AUDIT_RETENTION_DAYS through greentechhub-core's
AuditStore.prune, and keeps everything when it's 0."""

from datetime import UTC, datetime, timedelta

from greentechhub_core.audit import new_entry

from pyfinbot.core.settings import settings
from pyfinbot.pyfinbot import AUDIT_STORE, prune_audit_log

NOW = datetime(2026, 10, 16, 9, 0, tzinfo=UTC)
ACTOR = "prune-actor"


async def _actions():
    return sorted(e.action for e in await AUDIT_STORE.entries(actor=ACTOR, limit=50))


async def _record_old_and_new():
    await AUDIT_STORE.record(new_entry("prune.old", actor=ACTOR, now=NOW - timedelta(days=400)))
    await AUDIT_STORE.record(new_entry("prune.recent", actor=ACTOR, now=NOW - timedelta(days=30)))


async def test_entries_past_the_retention_are_pruned(gth_client, monkeypatch):
    monkeypatch.setattr(settings, "AUDIT_RETENTION_DAYS", 365)
    await _record_old_and_new()
    assert await prune_audit_log(now=NOW) >= 1
    assert await _actions() == ["prune.recent"]


async def test_zero_keeps_everything(gth_client, monkeypatch):
    monkeypatch.setattr(settings, "AUDIT_RETENTION_DAYS", 0)
    await _record_old_and_new()
    assert await prune_audit_log(now=NOW) == 0
    assert await _actions() == ["prune.old", "prune.recent"]
