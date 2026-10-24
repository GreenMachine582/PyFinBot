"""A user's own activity: their gth_audit_log entries (core/audit_events.py's
syncs and imports, and fastapi's sign-ins and settings changes) as rows for
greentechhub-ui's gth_timeline, newest first, a page at a time. The admin
audit log (/admin/audit) is where everyone's entries are read."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from greentechhub_core.audit import AuditStore

ACTIVITY_PAGE_SIZE = 10

#: gth_timeline's (icon, tone) per action prefix, over its own defaults for
#: auth / roles / settings.
ACTIVITY_KINDS = {
    "transactions": ("upload", "good"),
    "emails": ("envelope", "info"),
    "dividends": ("cash-coin", "good"),
    "stocks": ("arrow-repeat", "info"),
}


async def activity_page(store: AuditStore, subject: str, *, before: datetime | None = None,
                        limit: int = ACTIVITY_PAGE_SIZE) -> tuple[list[dict[str, Any]], datetime | None]:
    """Up to `limit` of `subject`'s entries older than `before`, and the
    cursor for the next page (None when this one wasn't full). Every row is
    theirs, so the actor shows as "You" rather than their account id; the
    target ("stock:12") is left out, since the summary already says it."""
    entries = await store.entries(actor=subject, before=before, limit=limit)
    rows = [{"at": e.at, "actor": "You", "action": e.action, "summary": e.summary, "target": None}
            for e in entries]
    return rows, entries[-1].at if len(entries) == limit else None
