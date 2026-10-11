"""PyFinBot's own audit-log entries (greentechhub-fastapi's audit(), into
the gth_audit_log store register_audit puts on the app): completed sync runs
and imports, recorded the same way from the web routes and the API. A run
refused before it starts (already running, not set up) isn't recorded.

The actor is the signed-in user (a page's session, or an API token), or
nobody for the API's unauthenticated market sync. Recording never fails the
request: fastapi logs a store error and carries on."""
from __future__ import annotations

from typing import Any, Sequence

from fastapi import Request
from greentechhub_fastapi.audit import audit


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}" + ("" if n == 1 else "s")


async def transactions_imported(request: Request, summary: Any, filename: str) -> None:
    """A spreadsheet import (core/transaction_import.py's summary)."""
    await audit(
        request, "transactions.imported",
        summary=f"Imported {summary.created} of {_plural(summary.total_rows, 'row')} from {filename or 'a file'}",
        details={"filename": filename, "total_rows": summary.total_rows, "created": summary.created,
                 "skipped": summary.skipped, "row_errors": len(summary.row_errors)},
    )


async def emails_synced(request: Request, summary: Any) -> None:
    """A Commsec email sync (core/commsec_import.py's summary)."""
    await audit(
        request, "emails.synced",
        summary=f"Imported {summary.created} of {_plural(summary.total_emails, 'email')}",
        details={"total_emails": summary.total_emails, "created": summary.created,
                 "skipped": summary.skipped, "errors": len(summary.errors)},
    )


async def dividends_synced(request: Request, stock_ids: Sequence[int], created: Sequence[Any],
                           updated: Sequence[Any], errors: Sequence[Any]) -> None:
    """A dividend sync over `stock_ids` (one picked stock is the target)."""
    await audit(
        request, "dividends.synced",
        target=("stock", stock_ids[0]) if len(stock_ids) == 1 else None,
        summary=f"{len(created)} new, {len(updated)} updated over {_plural(len(stock_ids), 'stock')}"
                + (f"; {len(errors)} failed" if errors else ""),
        details={"stocks": len(stock_ids), "created": len(created), "updated": len(updated),
                 "errors": len(errors)},
    )


async def market_synced(request: Request, market: str, created: Sequence[Any], updated: Sequence[Any],
                        archived: Sequence[Any]) -> None:
    """A market's stock-list sync (core/market_sync.py)."""
    await audit(
        request, "stocks.market_synced", target=("market", market),
        summary=f"{market}: {len(created)} created, {len(updated)} updated, {len(archived)} archived",
        details={"created": len(created), "updated": len(updated), "archived": len(archived)},
    )
