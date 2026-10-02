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
from ..core.errors import StatusError
from greentechhub_fastapi.settings import get_settings_service
from sqlmodel.ext.asyncio.session import AsyncSession

from ..core.commsec_import import EmailSyncError
from ..core.commsec_import import sync_commsec_emails as _sync_commsec_emails
from ..core.dependencies import get_current_user
from ..core.email_accounts import load_email_account
from ..core.email_sync import fetch_commsec_emails, mark_seen
from ..db.session import get_session
from ..models.user_models import User
from ..schemas.email_schemas import EmailSyncSummary

router = APIRouter(prefix="/emails", tags=["Emails"])


@router.post("/sync-commsec", response_model=EmailSyncSummary, status_code=status.HTTP_200_OK)
async def sync_commsec_emails(
    request: Request,
    include_seen: bool = Query(default=False, description="Reprocess already-\\Seen emails too (debugging)"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    try:
        user_id = current_user.id
        assert user_id is not None  # a stored user always has its primary key
        account = await load_email_account(get_settings_service(request), user_id)
        # fetch/mark passed from this module so tests can patch them here.
        return await _sync_commsec_emails(session, user_id, account, include_seen=include_seen,
                                          fetch=fetch_commsec_emails, mark=mark_seen)
    except EmailSyncError as exc:
        raise StatusError(exc.detail, status_code=exc.status_code, code="email_sync_failed")
