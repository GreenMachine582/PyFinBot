"""
Commsec email ingestion — POST /api/emails/sync-commsec pulls BOUGHT/SOLD
trade confirmation emails from the caller's own mailbox (their Settings ›
Email sync: IMAP, App Password auth) and creates Transaction rows. Manual
trigger only, matching POST /api/stocks/sync/{market}.
The import itself lives in core/commsec_import.py (shared with the web
Emails page).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from greentechhub_fastapi.settings import get_settings_service
from sqlmodel.ext.asyncio.session import AsyncSession
from greentechhub_core.identity import Identity
from greentechhub_fastapi.dependencies import get_current_identity

from ..core import audit_events
from ..core.commsec_import import sync_commsec_emails as _sync_commsec_emails
from ..core.email_accounts import load_email_account
from ..core.email_sync import fetch_commsec_emails, mark_seen
from ..db.session import get_session
from ..schemas.email_schemas import EmailSyncSummary

router = APIRouter(prefix="/emails", tags=["Emails"])


@router.post("/sync-commsec", response_model=EmailSyncSummary, status_code=status.HTTP_200_OK)
async def sync_commsec_emails(
    request: Request,
    include_seen: bool = Query(default=False, description="Reprocess already-\\Seen emails too (debugging)"),
    session: AsyncSession = Depends(get_session),
    identity: Identity = Depends(get_current_identity),
):
    # An EmailSyncError (503 not configured, 502 IMAP down, …) is answered by
    # the API's error handlers as an email_sync_failed envelope.
    user_id = identity.subject
    assert user_id is not None  # a stored user always has its primary key
    account = await load_email_account(get_settings_service(request), user_id)
    # fetch/mark passed from this module so tests can patch them here.
    summary = await _sync_commsec_emails(session, user_id, account, include_seen=include_seen,
                                         fetch=fetch_commsec_emails, mark=mark_seen)
    await audit_events.emails_synced(request, summary, recipient=identity.subject)
    return summary
