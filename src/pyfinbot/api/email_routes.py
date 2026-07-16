"""
Commsec email ingestion — POST /api/emails/sync-commsec pulls BOUGHT/SOLD
trade confirmation emails from Gmail (IMAP, App Password auth) and creates
Transaction rows. Manual trigger only, matching POST /api/stocks/sync/{market}.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from ..api.stock_routes import _searchForStock
from ..core.commsec_parser import CommsecParseError, parse_commsec_email
from ..core.dedupe import is_duplicate_transaction
from ..core.dependencies import get_current_user
from ..core.email_sync import (
    GmailNotConfiguredError,
    extract_body,
    fetch_commsec_emails,
    mark_seen,
    received_at,
)
from ..db.session import get_session
from ..models.transaction_models import Transaction, TypeEnum
from ..models.user_models import User
from ..schemas.email_schemas import EmailSyncSummary

router = APIRouter(prefix="/emails", tags=["Emails"])


@router.post("/sync-commsec", response_model=EmailSyncSummary, status_code=status.HTTP_200_OK)
async def sync_commsec_emails(
    include_seen: bool = Query(default=False, description="Reprocess already-\\Seen emails too (debugging)"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    try:
        messages = await asyncio.to_thread(fetch_commsec_emails, only_unseen=not include_seen)
    except GmailNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"IMAP fetch failed: {exc}")

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

        stock = await _searchForStock(session, f"ASX:{parsed.symbol}")
        if not stock:
            errors.append(f"UID {uid_label}: Stock 'ASX:{parsed.symbol}' not found")
            skipped += 1
            continue

        txn = Transaction(
            user_id=current_user.id,
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
        raise HTTPException(status_code=500, detail=f"Commit failed: {exc}")

    if processed_uids:
        try:
            await asyncio.to_thread(mark_seen, processed_uids)
        except Exception:
            pass  # non-fatal; content-dedup catches reprocessing on next sync

    return EmailSyncSummary(total_emails=len(messages), created=created, skipped=skipped, errors=errors)
