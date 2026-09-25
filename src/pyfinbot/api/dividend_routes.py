"""
POST /api/dividends/sync — pull dividend history (yfinance) for stocks the
calling user has ever transacted. Manual trigger only, no scheduler.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from ..core.dependencies import get_current_user
from ..core.dividend_sync import syncDividends, user_stock_ids
from ..db.session import get_session
from ..models.user_models import User
from ..schemas.dividend_schemas import DividendSyncResult

router = APIRouter(prefix="/dividends", tags=["Dividends"])


@router.post("/sync", response_model=DividendSyncResult, status_code=status.HTTP_200_OK)
async def sync_dividends(
    stock_id: Optional[int] = Query(
        default=None,
        description="Sync a single stock only; omit to sync every stock the caller has ever transacted",
    ),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    target_ids = [stock_id] if stock_id is not None else await user_stock_ids(session, current_user.id)

    created, updated, errors = await syncDividends(session, stock_ids=target_ids)
    return DividendSyncResult(created=created, updated=updated, errors=errors)
