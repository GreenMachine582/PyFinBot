"""
Commsec email ingestion — POST /api/emails/sync-commsec pulls BOUGHT/SOLD
trade confirmation emails from Gmail (IMAP, App Password auth) and creates
Transaction rows. Manual trigger only, matching POST /api/stocks/sync/{market}.
The import itself lives in core/commsec_import.py (shared with the web
Emails page).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from ..core.commsec_import import EmailSyncError
from ..core.commsec_import import sync_commsec_emails as _sync_commsec_emails
from ..core.dependencies import get_current_user
from ..core.email_sync import fetch_commsec_emails, mark_seen
from ..db.session import get_session
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
        # fetch/mark passed from this module so tests can patch them here.
        return await _sync_commsec_emails(session, current_user.id, include_seen=include_seen,
                                          fetch=fetch_commsec_emails, mark=mark_seen)
    except EmailSyncError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
