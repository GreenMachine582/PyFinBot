"""
Transaction import endpoint — accepts CSV or Excel files. The expected
columns and the import itself live in core/transaction_import.py (shared
with the web Import page).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlmodel.ext.asyncio.session import AsyncSession

from ..core.dependencies import get_current_user
from ..core.transaction_import import import_transactions as _import_transactions
from ..core.transaction_import import read_upload
from ..db.session import get_session
from ..models.user_models import User
from ..schemas.import_schemas import ImportSummary

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post(
    "/import",
    response_model=ImportSummary,
    status_code=status.HTTP_200_OK,
    summary="Bulk-import transactions from a CSV or Excel file",
)
async def import_transactions(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a CSV or Excel file to bulk-import transactions.

    Each row must include: date, stock (as MARKET:SYMBOL or symbol + separate market
    column), type, units, price. fees and notes are optional.

    Returns a summary of rows created, skipped, and any per-row errors.
    """
    # An ImportFileError (413 over 5 MB, 400 empty, …) is answered by the API's
    # error handlers as an import_failed envelope.
    content = await read_upload(file)
    user_id = current_user.id
    assert user_id is not None  # a stored user always has its primary key
    return await _import_transactions(session, user_id, content, file.filename or "")
