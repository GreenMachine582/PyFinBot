"""PyFinBot's own audit-log entries (greentechhub-fastapi's audit(), into
the gth_audit_log store register_audit puts on the app): completed sync runs
and imports, recorded the same way from the web routes and the API. A run
refused before it starts (already running, not set up) isn't recorded.

The actor is the signed-in user (a page's session, or an API token), or
nobody for the API's unauthenticated market sync. Recording never fails the
request: fastapi logs a store error and carries on.

Each also leaves an in-app notice (greentechhub-fastapi's notify, the
navbar bell) for `recipient`, the user who ran it, so a sync's result is
still there after its toast fades. Category "sync": each user picks
in-app, email, both or off at /settings › Notifications (core's
notification_preferences in core/user_settings.py); email goes to their
confirmed address. It never fails the request either."""
from __future__ import annotations

import logging
from typing import Any, Sequence

from fastapi import Request
from greentechhub_fastapi.audit import audit
from greentechhub_fastapi.notifications import notify
from greentechhub_ui import pluralise

logger = logging.getLogger(__name__)

NOTICE_CATEGORY = "sync"


def _kind(ok: int, problems: int) -> str:
    """The notice's tone: danger when nothing worked, warning when some did,
    success when all did, info when there was nothing to do."""
    if problems:
        return "warning" if ok else "danger"
    return "success" if ok else "info"


async def _notify(request: Request, recipient: str | None, title: str, message: str, kind: str) -> None:
    if recipient is None:
        return
    try:
        # notify takes toast()'s detail as a dict (toast() itself returns the
        # HX-Trigger JSON string).
        detail = {"message": message, "kind": kind, "title": title}
        await notify(request.app, recipient, detail, category=NOTICE_CATEGORY)
    except Exception:  # a notice must never fail the sync it reports
        logger.exception("could not leave a %r notice for %s", title, recipient)


async def transactions_imported(request: Request, summary: Any, filename: str,
                                recipient: str | None = None) -> None:
    """A spreadsheet import (core/transaction_import.py's summary)."""
    line = f"Imported {summary.created} of {pluralise(summary.total_rows, 'row')} from {filename or 'a file'}"
    await audit(
        request, "transactions.imported",
        summary=line,
        details={"filename": filename, "total_rows": summary.total_rows, "created": summary.created,
                 "skipped": summary.skipped, "row_errors": len(summary.row_errors)},
    )
    await _notify(request, recipient, "Import finished", line,
                  _kind(summary.created, summary.skipped + len(summary.row_errors)))


async def emails_synced(request: Request, summary: Any, recipient: str | None = None) -> None:
    """A Commsec email sync (core/commsec_import.py's summary)."""
    line = f"Imported {summary.created} of {pluralise(summary.total_emails, 'email')}"
    await audit(
        request, "emails.synced",
        summary=line,
        details={"total_emails": summary.total_emails, "created": summary.created,
                 "skipped": summary.skipped, "errors": len(summary.errors)},
    )
    await _notify(request, recipient, "Email sync finished", line,
                  _kind(summary.created, len(summary.errors)))


async def dividends_synced(request: Request, stock_ids: Sequence[int], created: Sequence[Any],
                           updated: Sequence[Any], errors: Sequence[Any],
                           recipient: str | None = None) -> None:
    """A dividend sync over `stock_ids` (one picked stock is the target)."""
    line = (f"{len(created)} new, {len(updated)} updated over {pluralise(len(stock_ids), 'stock')}"
            + (f"; {len(errors)} failed" if errors else ""))
    await audit(
        request, "dividends.synced",
        target=("stock", stock_ids[0]) if len(stock_ids) == 1 else None,
        summary=line,
        details={"stocks": len(stock_ids), "created": len(created), "updated": len(updated),
                 "errors": len(errors)},
    )
    await _notify(request, recipient, "Dividend sync finished", line,
                  _kind(len(created) + len(updated), len(errors)))


async def market_synced(request: Request, market: str, created: Sequence[Any], updated: Sequence[Any],
                        archived: Sequence[Any], recipient: str | None = None) -> None:
    """A market's stock-list sync (core/market_sync.py)."""
    line = f"{market}: {len(created)} created, {len(updated)} updated, {len(archived)} archived"
    await audit(
        request, "stocks.market_synced", target=("market", market),
        summary=line,
        details={"created": len(created), "updated": len(updated), "archived": len(archived)},
    )
    await _notify(request, recipient, f"{market} sync finished", line,
                  _kind(len(created) + len(updated) + len(archived), 0))
