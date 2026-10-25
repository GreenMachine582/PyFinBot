"""
Commsec email ingestion — turns BOUGHT/SOLD trade confirmation emails
(fetched over IMAP by core/email_sync.py) into Transaction rows. Shared by
POST /api/emails/sync-commsec and the web Emails page.
"""
from __future__ import annotations

import asyncio
from email.message import Message
from typing import Callable, List, Optional, Tuple

from greentechhub_core.types import ApplicationError
from sqlmodel.ext.asyncio.session import AsyncSession

from ..models.stock_models import Stock
from ..models.transaction_models import NOTES_MAX, Transaction, TypeEnum
from ..schemas.email_schemas import EmailSyncSummary
from greentechhub_core.email import message_text, received_at

from .commsec_parser import CommsecParseError, parse_commsec_email
from .dedupe import is_duplicate_transaction
from .email_sync import (
    EmailAccount,
    EmailNotConfiguredError,
    fetch_commsec_emails,
    mark_seen,
)


class EmailSyncError(ApplicationError):
    """The sync as a whole failed (not configured, IMAP down, commit failed).
    An ApplicationError with its HTTP status as the status_code hint, so the
    API's error handlers answer it ({code: "email_sync_failed", message}) and
    the web routes show its message."""

    code = "email_sync_failed"

    def __init__(self, status_code: int, message: str):
        super().__init__(message, status_code=status_code)


SyncProgress = Callable[[str, int, int], None]
"""progress(phase, done, total): phase "reading" (the mailbox; total 0 while
unknown) then "importing" (one call per email)."""


async def sync_commsec_emails(
    session: AsyncSession,
    user_id: str,
    account: EmailAccount,
    *,
    include_seen: bool = False,
    fetch: Optional[Callable[..., List[Tuple[bytes, Message]]]] = None,
    mark: Optional[Callable[[EmailAccount, List[bytes]], None]] = None,
    progress: Optional[SyncProgress] = None,
) -> EmailSyncSummary:
    """Import every parseable Commsec confirmation in `account` (that user's
    own mailbox) as `user_id`'s transaction and commit, then mark the
    processed emails \\Seen. Emails that can't be imported are skipped and
    reported; raises EmailSyncError when the sync as a whole fails.
    fetch/mark default to core.email_sync's IMAP functions, looked up per
    call so tests can patch them here. `progress`, if given, is told how far
    the sync has got (see SyncProgress)."""
    fetch = fetch or fetch_commsec_emails
    mark = mark or mark_seen
    report = progress or (lambda phase, done, total: None)
    report("reading", 0, 0)
    try:
        messages = await asyncio.to_thread(fetch, account, only_unseen=not include_seen)
    except EmailNotConfiguredError as exc:
        raise EmailSyncError(503, str(exc))
    except Exception as exc:
        raise EmailSyncError(502, f"IMAP fetch failed: {exc}")

    created = 0
    skipped = 0
    errors: list[str] = []
    processed_uids: list[bytes] = []

    for done, (uid, msg) in enumerate(messages):
        report("importing", done, len(messages))
        uid_label = uid.decode(errors="replace")
        try:
            body = message_text(msg)
            parsed = parse_commsec_email(msg.get("Subject", ""), body, received_at(msg))
        except (CommsecParseError, ValueError) as exc:
            errors.append(f"UID {uid_label}: parse error — {exc}")
            skipped += 1
            continue

        stock = await Stock.search(session, market="ASX", symbol=parsed.symbol)
        if not stock:
            # Not in the ASX company list (an ETF like VGE), or the list
            # isn't synced yet: add it under the email's company name.
            stock = Stock(market="ASX", symbol=parsed.symbol, name=parsed.company_name)
            session.add(stock)
            await session.flush()

        assert stock.id is not None  # loaded from, or flushed to, the database
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
            )[:NOTES_MAX],
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
    report("importing", len(messages), len(messages))

    try:
        await session.commit()
    except Exception as exc:
        await session.rollback()
        raise EmailSyncError(500, f"Commit failed: {exc}")

    if processed_uids:
        try:
            await asyncio.to_thread(mark, account, processed_uids)
        except Exception:
            pass  # non-fatal; content-dedup catches reprocessing on next sync

    return EmailSyncSummary(total_emails=len(messages), created=created, skipped=skipped, errors=errors)
