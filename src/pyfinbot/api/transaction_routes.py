from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, status
from fastapi_pagination import Page
from greentechhub_core.query.envelope import to_envelope
from greentechhub_core.query.types import Sort
from greentechhub_core.sqlalchemy.query import page
from greentechhub_core.types import BadRequestError, ForbiddenError, NotFoundError
from greentechhub_fastapi.query import PageParams
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..api.stock_routes import _searchForStock
from ..core.dependencies import get_current_user
from ..models.transaction_models import Transaction
from ..models.user_models import User
from ..schemas.transaction_schemas import TransactionCreate, TransactionRead, TransactionUpdate
from ..db.session import get_session
from .query import page_request

router = APIRouter(prefix="/transactions", tags=["Transactions"])

# What the list's `filters` and `sort` may name (public name -> column); the
# web table sorts through it too. Anything else is ignored. The list is
# always scoped to the signed-in user, so filtering on user_id can only narrow.
ALLOWED_FIELDS = {
    "id": Transaction.id,
    "user_id": Transaction.user_id,
    "stock_id": Transaction.stock_id,
    "type": Transaction.type,
    "units": Transaction.units,
    "price": Transaction.price,
    "fees": Transaction.fees,
    "total_value": Transaction.total_value,
    "cost": Transaction.cost,
    "fy": Transaction.fy,
    "transaction_date": Transaction.transaction_date,
    "date": Transaction.transaction_date,  # alias
    "create_datetime": Transaction.create_datetime,
    "write_datetime": Transaction.write_datetime,
}
DEFAULT_SORT = (Sort(field="transaction_date", direction="desc"), Sort(field="id"))


async def fetchTransaction(session: AsyncSession, transaction_id: int,
                         user_id: Optional[str] = None) -> Optional[Transaction]:
    """Fetch a transaction by ID."""
    stmt = (
        select(Transaction)
        .where(Transaction.id == transaction_id)
        .options(selectinload(Transaction.stock))
    )
    if user_id is not None:
        stmt = stmt.where(Transaction.user_id == user_id)

    result = await session.exec(stmt)
    return result.one_or_none()


@router.post("/", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    transaction_in: TransactionCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # If stock_id is string "market:symbol" → resolve to stock record
    stock = await _searchForStock(session, transaction_in.stock_id)
    if not stock:
        raise NotFoundError("Stock not found")
    transaction_in.stock_id = stock.id

    # Create new transaction object
    new_transaction = Transaction(**transaction_in.model_dump(), user_id=current_user.id)

    session.add(new_transaction)

    try:
        await session.commit()
        await session.refresh(new_transaction, attribute_names=["stock"])
    except IntegrityError:
        await session.rollback()
        raise BadRequestError("Failed to create transaction", code="create_failed")

    return new_transaction


@router.get("/", response_model=Page[TransactionRead])
async def list_transactions(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    params: PageParams = Depends(),
):
    """List the signed-in user's transactions: `page`/`size`, `sort`
    (default "-transaction_date,id"), and `filters` / `filter` on the fields
    in ALLOWED_FIELDS (api/query.py)."""
    stmt = (
        select(Transaction)
        .options(selectinload(Transaction.stock))  # eager-load nested stock
        .where(Transaction.user_id == current_user.id)  # hard user scope
    )
    result = await page(session, stmt, page_request(params), ALLOWED_FIELDS, default_sort=DEFAULT_SORT)
    return to_envelope(result)


@router.get("/{transaction_id:int}", response_model=TransactionRead)
async def get_transaction(
    transaction_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if not (transaction := await fetchTransaction(session, transaction_id)):
        raise NotFoundError("Transaction not found")

    if transaction.user_id != current_user.id:
        raise ForbiddenError("Not allowed to access this transaction")

    return transaction


@router.put("/{transaction_id:int}", response_model=TransactionRead)
async def update_transaction(
    transaction_id: int,
    transaction_update: TransactionUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if not (transaction := await fetchTransaction(session, transaction_id)):
        raise NotFoundError("Transaction not found")

    if transaction.user_id != current_user.id:
        raise ForbiddenError("Not allowed to modify this transaction")

    # An explicit null only makes sense for notes; for anything else it would
    # break recompute(), so treat it the same as "not sent".
    changes = {
        key: value for key, value in transaction_update.model_dump(exclude_unset=True).items()
        if value is not None or key == "notes"
    }
    if "stock_id" in changes:
        stock = await _searchForStock(session, changes["stock_id"])
        if not stock:
            raise NotFoundError("Stock not found")
        changes["stock_id"] = stock.id

    for key, value in changes.items():
        setattr(transaction, key, value)
    transaction.recompute()
    transaction.write_datetime = datetime.now(timezone.utc)

    session.add(transaction)
    try:
        await session.commit()
        await session.refresh(transaction, attribute_names=["stock"])
    except IntegrityError:
        await session.rollback()
        raise BadRequestError("Failed to update transaction", code="update_failed")

    return transaction


@router.delete("/{transaction_id:int}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    transaction = await session.get(Transaction, transaction_id)
    if not transaction:
        raise NotFoundError("Transaction not found")

    if transaction.user_id != current_user.id:
        raise ForbiddenError("Not allowed to delete this transaction")

    await session.delete(transaction)
    await session.commit()
