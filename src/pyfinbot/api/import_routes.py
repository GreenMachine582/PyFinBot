"""
Transaction import endpoint — accepts CSV or Excel files. The expected
columns and the import itself live in core/transaction_import.py (shared
with the web Import page).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from sqlmodel.ext.asyncio.session import AsyncSession
from greentechhub_core.identity import Identity
from greentechhub_fastapi.dependencies import get_current_identity
from greentechhub_fastapi.uploads import read_upload

from ..core import audit_events
from ..core.transaction_import import import_transactions as _import_transactions
from ..core.transaction_import import MAX_UPLOAD_BYTES
from ..db.session import get_session
from ..schemas.import_schemas import ImportSummary

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post(
    "/import",
    response_model=ImportSummary,
    status_code=status.HTTP_200_OK,
    summary="Bulk-import transactions from a CSV or Excel file",
)
async def import_transactions(
    request: Request,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    identity: Identity = Depends(get_current_identity),
):
    """
    Upload a CSV or Excel file to bulk-import transactions.

    Each row must include: date, stock (as MARKET:SYMBOL or symbol + separate market
    column), type, units, price. fees and notes are optional.

    Returns a summary of rows created, skipped, and any per-row errors.
    """
    # The API's error handlers answer both: a file over 5 MB is fastapi's 413
    # payload_too_large; one that can't be imported (400 empty, 422 unparseable,
    # …) is an ImportFileError, import_failed.
    content = await read_upload(file, limit=MAX_UPLOAD_BYTES)
    user_id = identity.subject
    assert user_id is not None  # a stored user always has its primary key
    summary = await _import_transactions(session, user_id, content, file.filename or "")
    await audit_events.transactions_imported(request, summary, file.filename or "",
                                             recipient=identity.subject)
    return summary
