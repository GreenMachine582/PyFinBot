"""
Commsec email ingestion — turns BOUGHT/SOLD trade confirmation emails
(fetched over IMAP by core/email_sync.py) into Transaction rows. Shared by
POST /api/emails/sync-commsec and the web Emails page.
"""
from __future__ import annotations

import asyncio
from email.message import Message
from typing import Callable, List, Optional, Tuple

from sqlmodel.ext.asyncio.session import AsyncSession

from ..models.stock_models import Stock
from ..models.transaction_models import Transaction, TypeEnum
from ..schemas.email_schemas import EmailSyncSummary
from .commsec_parser import CommsecParseError, parse_commsec_email
from .dedupe import is_duplicate_transaction
from .email_sync import (
    GmailNotConfiguredError,
    extract_body,
    fetch_commsec_emails,
    mark_seen,
    received_at,
)


class EmailSyncError(Exception):
    """The sync as a whole failed (not configured, IMAP down, commit failed).
    status_code is the HTTP status the API maps it to."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


async def sync_commsec_emails(
    session: AsyncSession,
    user_id: str,
    *,
    include_seen: bool = False,
    fetch: Optional[Callable[..., List[Tuple[bytes, Message]]]] = None,
    mark: Optional[Callable[[List[bytes]], None]] = None,
) -> EmailSyncSummary:
    """Import every parseable Commsec confirmation as `user_id`'s transaction
    and commit, then mark the processed emails \\Seen. Emails that can't be
    imported are skipped and reported; raises EmailSyncError when the sync
    as a whole fails. fetch/mark default to core.email_sync's IMAP
    functions, looked up per call so tests can patch them here."""
    fetch = fetch or fetch_commsec_emails
    mark = mark or mark_seen
    try:
        messages = await asyncio.to_thread(fetch, only_unseen=not include_seen)
    except GmailNotConfiguredError as exc:
        raise EmailSyncError(503, str(exc))
    except Exception as exc:
        raise EmailSyncError(502, f"IMAP fetch failed: {exc}")

    created = 0
    skipped = 0
    errors: list[str] = []
    processed_uids: list[bytes] = []

    for uid, msg in messages:
        uid_label = uid.decode(errors="replace")
        try:
            body = extract_body(msg)
            parsed = parse_commsec_email(msg.get("Subject", ""), body, received_at(msg))
        except (CommsecParseError, ValueError) as exc:
            errors.append(f"UID {uid_label}: parse error — {exc}")
            skipped += 1
            continue

        stock = await Stock.search(session, market="ASX", symbol=parsed.symbol)
        if not stock:
            errors.append(f"UID {uid_label}: Stock 'ASX:{parsed.symbol}' not found")
            skipped += 1
            continue

        txn = Transaction(
            user_id=user_id,
            stock_id=stock.id,
            transaction_date=parsed.trade_date,
            type=TypeEnum.BUY if parsed.action == "BOUGHT" else TypeEnum.SELL,
            units=parsed.units,
            price=parsed.price_per_unit,
            fees=parsed.brokerage,
            notes=(
                f"Commsec email import — {parsed.action} {parsed.units} {parsed.symbol} "
                f"on {parsed.trade_date}, trading account {parsed.trading_account}"
            ),
        )

        try:
            if await is_duplicate_transaction(session, txn):
                errors.append(f"UID {uid_label}: Duplicate transaction (matches an existing one), skipped")
                skipped += 1
            else:
                session.add(txn)
                await session.flush()
                created += 1
            processed_uids.append(uid)
        except Exception as exc:
            await session.rollback()
            errors.append(f"UID {uid_label}: {exc}")
            skipped += 1

    try:
        await session.commit()
    except Exception as exc:
        await session.rollback()
        raise EmailSyncError(500, f"Commit failed: {exc}")

    if processed_uids:
        try:
            await asyncio.to_thread(mark, processed_uids)
        except Exception:
            pass  # non-fatal; content-dedup catches reprocessing on next sync

    return EmailSyncSummary(total_emails=len(messages), created=created, skipped=skipped, errors=errors)
