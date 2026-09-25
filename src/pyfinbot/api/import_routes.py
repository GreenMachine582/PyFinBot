"""
Transaction import endpoint — accepts CSV or Excel files. The expected
columns and the import itself live in core/transaction_import.py (shared
with the web Import page).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlmodel.ext.asyncio.session import AsyncSession

from ..core.dependencies import get_current_user
from ..core.transaction_import import ImportFileError, import_transactions as _import_transactions
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
    try:
        return await _import_transactions(session, current_user.id, await file.read(), file.filename or "")
    except ImportFileError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
