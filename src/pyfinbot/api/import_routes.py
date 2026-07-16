"""
Transaction import endpoint — accepts CSV or Excel files.

Expected columns (case-insensitive, whitespace-stripped):
  date        Transaction date. Formats: dd/MM/yyyy or yyyy-MM-dd.
  stock       Stock identifier: "MARKET:SYMBOL" (e.g. "ASX:BHP") or plain symbol
              when market column is also present.
  market      (Optional) Market code. Used when stock column holds only symbol.
  type        "Buy" or "Sell" (case-insensitive).
  units       Number of units traded.
  price       Price per unit.
  fees        (Optional) Brokerage / commission. Defaults to 0.
  notes       (Optional) Free-text notes.
"""
from __future__ import annotations

import io

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlmodel.ext.asyncio.session import AsyncSession

from ..api.stock_routes import _searchForStock
from ..core.dedupe import is_duplicate_transaction as _is_duplicate
from ..core.dependencies import get_current_user
from ..db.session import get_session
from ..models.transaction_models import Transaction, TypeEnum
from ..models.user_models import User
from ..schemas.import_schemas import ImportSummary
from ..schemas.transaction_schemas import parse_transaction_date

router = APIRouter(prefix="/transactions", tags=["Transactions"])

# Column aliases: canonical name -> accepted alternatives
_COLUMN_ALIASES: dict[str, list[str]] = {
    "date": ["date", "transaction_date", "trade_date"],
    "stock": ["stock", "ticker", "code", "stock_code"],
    "market": ["market", "exchange"],
    "type": ["type", "transaction_type", "action"],
    "units": ["units", "qty", "quantity", "shares"],
    "price": ["price", "unit_price", "trade_price"],
    "fees": ["fees", "fee", "commission", "brokerage"],
    "notes": ["notes", "note", "comment", "comments"],
}


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename DataFrame columns to canonical names using the alias map."""
    col_map = {}
    lowered = {c.strip().lower(): c for c in df.columns}
    for canonical, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lowered:
                col_map[lowered[alias]] = canonical
                break
    return df.rename(columns=col_map)


def _parse_dataframe(content: bytes, filename: str) -> pd.DataFrame:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ("xls", "xlsx", "xlsm"):
        df = pd.read_excel(io.BytesIO(content))
    else:
        # Try CSV; tolerate BOM
        df = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
    df = _normalise_columns(df)
    # Empty cells surface as NaN (truthy, unlike None), which breaks the
    # `value or default` fallbacks below and NOT NULL columns like `fees`.
    # Numeric columns silently coerce None back to NaN unless cast to
    # object dtype first, since float64 arrays have no Python-None slot.
    return df.astype(object).where(pd.notna(df), None)


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
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        df = _parse_dataframe(content, file.filename or "")
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse file: {exc}")

    required = {"date", "stock", "type", "units", "price"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Missing required columns: {sorted(missing)}. "
                   f"Got: {sorted(df.columns.tolist())}",
        )

    created = 0
    skipped = 0
    errors: list[str] = []

    for row_num, row in enumerate(df.itertuples(index=False), start=2):
        row_label = f"Row {row_num}"
        try:
            # Resolve stock identifier
            stock_val = str(getattr(row, "stock", "")).strip()
            market_val = str(getattr(row, "market", "")).strip().upper()

            if ":" in stock_val:
                stock_id_str = stock_val.upper()
            elif market_val:
                stock_id_str = f"{market_val}:{stock_val.upper()}"
            else:
                errors.append(f"{row_label}: 'stock' must be MARKET:SYMBOL or include a 'market' column")
                skipped += 1
                continue

            stock = await _searchForStock(session, stock_id_str)
            if not stock:
                errors.append(f"{row_label}: Stock '{stock_id_str}' not found")
                skipped += 1
                continue

            # Parse type
            try:
                tx_type = TypeEnum(str(getattr(row, "type", "")).strip())
            except ValueError:
                errors.append(f"{row_label}: Invalid type '{getattr(row, 'type', '')}'")
                skipped += 1
                continue

            # Parse date
            try:
                tx_date = parse_transaction_date(str(getattr(row, "date", "")).strip())
            except ValueError as exc:
                errors.append(f"{row_label}: {exc}")
                skipped += 1
                continue

            # Build transaction
            txn = Transaction(
                user_id=current_user.id,
                stock_id=stock.id,
                transaction_date=tx_date,
                type=tx_type,
                units=float(getattr(row, "units")),
                price=float(getattr(row, "price")),
                fees=float(getattr(row, "fees", 0) or 0),
                notes=str(getattr(row, "notes", "") or "").strip() or None,
            )

            if await _is_duplicate(session, txn):
                errors.append(f"{row_label}: Duplicate transaction (matches an existing one), skipped")
                skipped += 1
                continue

            session.add(txn)
            await session.flush()  # catch DB errors per row
            created += 1

        except Exception as exc:
            await session.rollback()
            errors.append(f"{row_label}: {exc}")
            skipped += 1
            continue

    try:
        await session.commit()
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Commit failed: {exc}")

    return ImportSummary(
        total_rows=len(df),
        created=created,
        skipped=skipped,
        errors=errors,
    )
