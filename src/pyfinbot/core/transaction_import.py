"""
Bulk transaction import from CSV or Excel — shared by the API route
(`POST /api/transactions/import`) and the web Import page.

Expected columns (case-insensitive, whitespace-stripped; see COLUMN_ALIASES
for accepted alternative names):
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
from sqlmodel.ext.asyncio.session import AsyncSession

from ..models.stock_models import Stock
from ..models.transaction_models import Transaction, TypeEnum
from ..schemas.import_schemas import ImportRowError, ImportSummary
from ..schemas.transaction_schemas import parse_transaction_date
from .dedupe import is_duplicate_transaction

ACCEPTED_EXTENSIONS = (".csv", ".xls", ".xlsx", ".xlsm")
REQUIRED_COLUMNS = ("date", "stock", "type", "units", "price")

# Column aliases: canonical name -> accepted alternatives
COLUMN_ALIASES: dict[str, list[str]] = {
    "date": ["date", "transaction_date", "trade_date"],
    "stock": ["stock", "ticker", "code", "stock_code"],
    "market": ["market", "exchange"],
    "type": ["type", "transaction_type", "action"],
    "units": ["units", "qty", "quantity", "shares"],
    "price": ["price", "unit_price", "trade_price"],
    "fees": ["fees", "fee", "commission", "brokerage"],
    "notes": ["notes", "note", "comment", "comments"],
}


class ImportFileError(Exception):
    """The file as a whole can't be imported (empty, unparseable, missing
    columns, commit failure). status_code is the HTTP status the API maps it to."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename DataFrame columns to canonical names using the alias map."""
    col_map = {}
    lowered = {c.strip().lower(): c for c in df.columns}
    for canonical, aliases in COLUMN_ALIASES.items():
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


async def import_transactions(session: AsyncSession, user_id: str, content: bytes,
                              filename: str) -> ImportSummary:
    """Import every valid row of a CSV/Excel file as `user_id`'s transactions
    and commit. Bad rows are skipped and reported; raises ImportFileError
    when the file as a whole can't be imported."""
    if not content:
        raise ImportFileError(400, "Uploaded file is empty")

    try:
        df = _parse_dataframe(content, filename)
    except Exception as exc:
        raise ImportFileError(422, f"Could not parse file: {exc}")

    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ImportFileError(
            422,
            f"Missing required columns: {sorted(missing)}. "
            f"Got: {sorted(df.columns.tolist())}",
        )

    created = 0
    row_errors: list[ImportRowError] = []

    for row_num, row in enumerate(df.itertuples(index=False), start=2):
        def skip(message: str) -> None:
            row_errors.append(ImportRowError(row=row_num, message=message))

        # Resolve stock identifier
        stock_val = str(getattr(row, "stock", "")).strip()
        market_val = str(getattr(row, "market", "")).strip().upper()

        if ":" in stock_val:
            stock_id_str = stock_val.upper()
        elif market_val:
            stock_id_str = f"{market_val}:{stock_val.upper()}"
        else:
            skip("'stock' must be MARKET:SYMBOL or include a 'market' column")
            continue

        market, _, symbol = stock_id_str.partition(":")
        stock = await Stock.search(session, market=market, symbol=symbol)
        if not stock:
            skip(f"Stock '{stock_id_str}' not found")
            continue

        # Parse type
        try:
            tx_type = TypeEnum(str(getattr(row, "type", "")).strip())
        except ValueError:
            skip(f"Invalid type '{getattr(row, 'type', '')}'")
            continue

        # Parse date
        try:
            tx_date = parse_transaction_date(str(getattr(row, "date", "")).strip())
        except ValueError as exc:
            skip(str(exc))
            continue

        # Parse numbers — before anything touches the session, so a bad value
        # is just a skipped row rather than a rollback (which would also
        # discard the rows already flushed from this file).
        try:
            units = float(getattr(row, "units"))
            price = float(getattr(row, "price"))
            fees = float(getattr(row, "fees", 0) or 0)
        except (TypeError, ValueError):
            skip("'units', 'price' and 'fees' must be numbers")
            continue

        txn = Transaction(
            user_id=user_id,
            stock_id=stock.id,
            transaction_date=tx_date,
            type=tx_type,
            units=units,
            price=price,
            fees=fees,
            notes=str(getattr(row, "notes", "") or "").strip() or None,
        )

        if await is_duplicate_transaction(session, txn):
            skip("Duplicate transaction (matches an existing one), skipped")
            continue

        try:
            session.add(txn)
            await session.flush()  # catch DB errors per row
        except Exception as exc:
            await session.rollback()
            skip(str(exc))
            continue
        created += 1

    try:
        await session.commit()
    except Exception as exc:
        await session.rollback()
        raise ImportFileError(500, f"Commit failed: {exc}")

    return ImportSummary(
        total_rows=len(df),
        created=created,
        skipped=len(row_errors),
        errors=[f"Row {e.row}: {e.message}" for e in row_errors],
        row_errors=row_errors,
    )
