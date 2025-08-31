from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlmodel import paginate
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


from ..api.stock_routes import _searchForStock
from ..core.sa_filters_compat import buildWhereFromSAFSpec
from ..core.sorting import buildSortOrderBy
from ..models.user_models import User
from ..core.dependacies import x_user_id_dep
from ..models.transaction_models import Transaction
from ..schemas.transaction_schemas import TransactionCreate, TransactionRead, TransactionUpdate
from ..db.session import get_session

router = APIRouter(prefix="/transactions", tags=["Transactions"])

# Allowed field map (external -> model attribute). Add/adjust to match your Transaction model.
# Unknown fields in filters/sorters will be ignored by the helpers.
ALLOWED_FILTERING_FIELDS = {
    "id": "id",
    "user_id": "user_id",
    "stock_id": "stock_id",
    "type": "type",
    "units": "units",
    "price": "price",
    "fees": "fees",
    "total_value": "total_value",
    "cost": "cost",
    "fy": "fy",
    "transaction_date": "transaction_date",
    "date": "transaction_date",  # alias
    "create_datetime": "create_datetime",
    "write_datetime": "write_datetime",
}


async def fetchTransaction(session: AsyncSession, transaction_id: int,
                         user_id: Optional[int] = None) -> Optional[Transaction]:
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


async def _ensureUser(session: AsyncSession, user_id: str) -> User:
    user = await session.get(User, user_id)
    if user:
        return user
    user = User(id=user_id, active=True)
    session.add(user)
    # Commit here (or let outer commit handle it). Committing now helps avoid
    # a later FK violation if something goes wrong after adding the transaction.
    try:
        await session.commit()
    except IntegrityError:
        # concurrent create won the race: safe to ignore, just rollback to clear state
        await session.rollback()
    return user


@router.post("/", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    transaction_in: TransactionCreate,
    session: AsyncSession = Depends(get_session),
    header_user_id: Optional[str] = Depends(x_user_id_dep),
):
    # Resolve user_id: prefer body, else header
    resolved_user_id = transaction_in.user_id or header_user_id
    if not resolved_user_id:
        raise HTTPException(status_code=400, detail="user_id not provided in body or X-User-ID header")

    # Ensure user exists (create if missing)
    await _ensureUser(session, resolved_user_id)
    transaction_in.user_id = resolved_user_id

    # If stock_id is string "market:symbol" → resolve to stock record
    stock = await _searchForStock(session, transaction_in.stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    transaction_in.stock_id = stock.id

    # Create new transaction object
    new_transaction = Transaction(**transaction_in.model_dump())

    session.add(new_transaction)

    try:
        await session.commit()
        await session.refresh(new_transaction, attribute_names=["stock"])
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Failed to create transaction")

    return new_transaction


@router.get("/", response_model=Page[TransactionRead])
async def list_transactions(
    session: AsyncSession = Depends(get_session),
    header_user_id: Optional[str] = Depends(x_user_id_dep),

    # Complex filters: sqlalchemy-filters schema (JSON string)
    filters: Optional[str] = Query(
        None, description="sqlalchemy-filters JSON spec"
    ),

    # Tabulator sends sorters as JSON list; keep 'sort' too for compatibility
    sorters: Optional[str] = Query(None, description="Tabulator sorters JSON"),
    sort: Optional[str] = Query(
        "-transaction_date,id",
        description="Comma list of fields, '-' for desc (fallback if no sorters)",
    ),
):
    """
    List transactions with optional filtering/sorting.

    - `filters`: JSON per sqlalchemy-filters (AND/OR groups, ops, etc.)
    - `sorters`: Tabulator sorters JSON (list of {field, dir})
    - `sort`:    Simple fallback (e.g. "-transaction_date,id")
    - If `X-User-ID` header is present, results are hard-filtered to that user.
    """
    # Require X-User-ID
    if not header_user_id:
        raise HTTPException(status_code=400, detail="X-User-ID header is required")

    stmt = (
        select(Transaction)
        .options(selectinload(Transaction.stock))  # eager-load nested stock
    )
    # Hard user scope (AND)
    stmt = stmt.where(Transaction.user_id == header_user_id)

    # Parse + apply sqlalchemy-filters
    if filters:
        try:
            filters_spec = json.loads(filters)
        except json.JSONDecodeError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid 'filters' JSON")

        # If a client tries to filter a different user_id, override it with header value
        # by appending (AND) our user filter afterwards.
        where_expr = buildWhereFromSAFSpec(
            model=Transaction, spec=filters_spec, allowed_fields=ALLOWED_FILTERING_FIELDS
        )
        if where_expr is not None:
            stmt = stmt.where(where_expr)

    # Sorting (Tabulator sorters > fallback 'sort')
    order_by = buildSortOrderBy(Transaction, ALLOWED_FILTERING_FIELDS, sorters, sort)
    if order_by:
        stmt = stmt.order_by(*order_by)

    return await paginate(session, stmt)


@router.get("/{transaction_id}", response_model=TransactionRead)
async def get_transaction(
    transaction_id: int,
    session: AsyncSession = Depends(get_session),
    header_user_id: Optional[int] = Depends(x_user_id_dep),
):
    if not (transaction := await fetchTransaction(session, transaction_id)):
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Enforce ownership if header is present
    if header_user_id is not None and transaction.user_id != header_user_id:
        raise HTTPException(status_code=403, detail="Not allowed to access this transaction")

    return transaction


@router.put("/{transaction_id}", response_model=TransactionRead)
async def update_transaction(
    transaction_id: int,
    transaction_update: TransactionUpdate,
    session: AsyncSession = Depends(get_session),
    header_user_id: Optional[int] = Depends(x_user_id_dep),
):
    if not (transaction := await fetchTransaction(session, transaction_id)):
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Enforce ownership if header is present
    if header_user_id is not None and transaction.user_id != header_user_id:
        raise HTTPException(status_code=403, detail="Not allowed to modify this transaction")

    for key, value in transaction_update.model_dump(exclude_unset=True).items():
        setattr(transaction, key, value)

    session.add(transaction)
    try:
        await session.commit()
        await session.refresh(transaction, attribute_names=["stock"])
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Failed to update transaction")

    return transaction


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: int,
    session: AsyncSession = Depends(get_session),
    header_user_id: Optional[int] = Depends(x_user_id_dep),
):
    transaction = await session.get(Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Enforce ownership if header is present
    if header_user_id is not None and transaction.user_id != header_user_id:
        raise HTTPException(status_code=403, detail="Not allowed to delete this transaction")

    await session.delete(transaction)
    await session.commit()
