"""Shared duplicate-transaction detection, used by CSV/Excel import and
Commsec email import so both content-dedup checks stay identical."""
from __future__ import annotations

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..models.transaction_models import Transaction


async def is_duplicate_transaction(session: AsyncSession, txn: Transaction) -> bool:
    """Whether a transaction with the same content already exists (this
    upload or a prior one) — notes/id/derived fields are not part of identity."""
    stmt = select(Transaction).where(
        Transaction.user_id == txn.user_id,
        Transaction.stock_id == txn.stock_id,
        Transaction.transaction_date == txn.transaction_date,
        Transaction.type == txn.type,
        Transaction.units == txn.units,
        Transaction.price == txn.price,
        Transaction.fees == txn.fees,
    )
    result = await session.exec(stmt)
    return result.first() is not None
