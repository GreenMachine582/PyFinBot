from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..models.transaction_models import Transaction
from ..api.stock_routes import _searchForStock
from ..schemas.transaction_schemas import TransactionCreate, TransactionRead, TransactionUpdate
from ..db.session import get_session

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("/", response_model=TransactionRead)
async def create_transaction(transaction_in: TransactionCreate, session: AsyncSession = Depends(get_session)):
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
        await session.refresh(new_transaction)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Failed to create transaction")

    return new_transaction


@router.get("/", response_model=list[TransactionRead])
async def list_transactions(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Transaction))
    return result.all()


@router.get("/{transaction_id}", response_model=TransactionRead)
async def get_transaction(transaction_id: int, session: AsyncSession = Depends(get_session)):
    transaction = await session.get(Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@router.put("/{transaction_id}", response_model=TransactionRead)
async def update_transaction(
    transaction_id: int,
    transaction_update: TransactionUpdate,
    session: AsyncSession = Depends(get_session)
):
    transaction = await session.get(Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    for key, value in transaction_update.model_dump(exclude_unset=True).items():
        setattr(transaction, key, value)

    session.add(transaction)
    try:
        await session.commit()
        await session.refresh(transaction)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Failed to update transaction")

    return transaction


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(transaction_id: int, session: AsyncSession = Depends(get_session)):
    transaction = await session.get(Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    await session.delete(transaction)
    await session.commit()
