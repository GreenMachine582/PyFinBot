from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from greentechhub_core.identity import Identity
from greentechhub_core.query.types import Sort
from greentechhub_core.sqlalchemy.query import order_by, paginate
from greentechhub_fastapi.downloads import csv_download, csv_value
from greentechhub_fastapi.forms import field_errors
from greentechhub_fastapi.settings import get_effective_settings
from greentechhub_ui import TableState
from greentechhub_ui.htmx import wants_fragment
from pydantic import ValidationError
from sqlalchemy import delete
from sqlalchemy.orm import selectinload
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ...api.transaction_routes import ALLOWED_FIELDS, fetchTransaction
from ...core.user_settings import DEFAULT_ROWS_PER_PAGE, PAGE_SIZES
from ...db.session import get_session
from ...models.stock_models import Stock
from ...models.transaction_models import Transaction, TypeEnum
from ...schemas.transaction_schemas import TransactionCreate
from ..deps import page_identity
from ..htmx import CLOSE_MODAL, hx_response
from ..templating import templates

router = APIRouter(prefix="/transactions")

CHANGED = "transactionsChanged"
# stock_id_search is the stock gth_combobox's visible text — only echoed back
# on a 422 re-render; stock_id (the picked value) is what's validated.
FORM_FIELDS = ("stock_id", "stock_id_search", "transaction_date", "type", "units", "price", "fees", "notes")


async def _get_transaction_or_404(session: AsyncSession, transaction_id: int, identity: Identity) -> Transaction:
    # Scoped by user in the query itself, so another user's id is
    # indistinguishable from a missing one (404, not 403).
    transaction = await fetchTransaction(session, transaction_id, user_id=identity.subject)
    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return transaction


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _table_state(request: Request, user_settings: dict[str, Any]) -> TableState:
    return TableState.from_query(
        request.query_params,
        user_settings=user_settings,  # their rows per page
        id="transactions",
        base_url="/transactions",
        page_size=DEFAULT_ROWS_PER_PAGE,
        page_sizes=PAGE_SIZES,
        sortable=("transaction_date", "type", "units", "price", "fees", "total_value", "cost"),
        default_sort="transaction_date",
        default_direction="desc",
        filter_params=("stock", "type", "fy", "date_from", "date_to"),
        # gth_data_table's "Export CSV" link: this endpoint with the current
        # filters and sort, never page or size.
        export_base_url="/transactions.csv",
    )


def _transactions_stmt(identity: Identity, state: TableState) -> Any:
    """The user's transactions with the table's filters and sort: paged for
    the table, whole for the CSV export."""
    stmt = (
        select(Transaction)
        .options(selectinload(Transaction.stock))  # type: ignore[arg-type]  # SQLModel types a Relationship as its model
        .where(Transaction.user_id == identity.subject)
    )
    filters = state.filters
    if stock := filters.get("stock"):
        like = f"%{stock}%"
        stmt = stmt.join(Stock).where(col(Stock.symbol).ilike(like) | col(Stock.name).ilike(like))
    if (type_ := filters.get("type")) in {t.value for t in TypeEnum}:
        stmt = stmt.where(Transaction.type == TypeEnum(type_))
    if start := _parse_date(filters.get("date_from", "")):
        stmt = stmt.where(Transaction.transaction_date >= start)
    if end := _parse_date(filters.get("date_to", "")):
        stmt = stmt.where(Transaction.transaction_date <= end)
    if (fy := filters.get("fy", "")).isdigit():
        stmt = stmt.where(Transaction.fy == int(fy))
    # The table's sort, then tie-breakers in the same direction so paging is stable.
    sorts = [Sort(field=f, direction=state.direction) for f in (state.sort, "transaction_date", "id") if f]
    return stmt.order_by(*order_by(sorts, ALLOWED_FIELDS))


async def _query_transactions(session: AsyncSession, identity: Identity,
                              state: TableState) -> tuple[list[Transaction], TableState]:
    transactions, total = await paginate(session, _transactions_stmt(identity, state),
                                         offset=state.offset, limit=state.limit)
    return list(transactions), state.with_result(total=total)


CSV_HEADER = ["Date", "Market", "Symbol", "Type", "Units", "Price", "Fees", "Total", "Cost", "FY", "Notes"]


@router.get(".csv")
async def export_csv(
    request: Request,
    identity: Identity = Depends(page_identity),
    session: AsyncSession = Depends(get_session),
    user_settings: dict[str, Any] = Depends(get_effective_settings),
):
    """Every transaction the table's current filters and sort match, as a CSV
    download — the table's "Export CSV" link (TableState.export_url)."""
    state = _table_state(request, user_settings)
    transactions = (await session.exec(_transactions_stmt(identity, state))).all()
    fy_label = templates.env.filters["fy"]
    rows = [CSV_HEADER, *(
        [t.transaction_date.isoformat(), t.stock.market, t.stock.symbol, t.type.value,
         csv_value(t.units), csv_value(t.price), csv_value(t.fees), csv_value(t.total_value), csv_value(t.cost),
         fy_label(t.fy), t.notes or ""]
        for t in transactions
    )]
    return csv_download(rows, "pyfinbot-transactions.csv")


@router.get("")
async def transactions_page(
    request: Request,
    identity: Identity = Depends(page_identity),
    session: AsyncSession = Depends(get_session),
    user_settings: dict[str, Any] = Depends(get_effective_settings),
):
    """The page, or (htmx: sort, filter, load more, refresh) just the table."""
    transactions, state = await _query_transactions(session, identity, _table_state(request, user_settings))
    context = {"table": state, "transactions": transactions}
    if wants_fragment(request.headers):
        return templates.TemplateResponse(request, "_transaction_table.html", context)
    fys = (await session.exec(
        select(Transaction.fy).where(Transaction.user_id == identity.subject).distinct().order_by(col(Transaction.fy).desc())
    )).all()
    return templates.TemplateResponse(request, "transactions.html", {
        **context, "fys": fys, "types": [t.value for t in TypeEnum],
    })


async def _render_form(request: Request, session: AsyncSession, transaction: Transaction | None, values: dict,
                       errors: dict, *, template: str, status_code: int = status.HTTP_200_OK):
    # The combobox shows the picked stock's label; with no (valid) pick it
    # falls back to whatever search text was typed.
    stock_id = str(values.get("stock_id") or "")
    selected_stock = await session.get(Stock, int(stock_id)) if stock_id.isdigit() else None
    return templates.TemplateResponse(request, template, {
        "transaction": transaction,
        "values": values,
        "errors": errors,
        "selected_stock": selected_stock,
    }, status_code=status_code)


@router.get("/new")
async def new_transaction_form(request: Request, identity: Identity = Depends(page_identity),
                               session: AsyncSession = Depends(get_session)):
    values = {"transaction_date": date.today().isoformat(), "type": TypeEnum.BUY.value, "fees": "0"}
    return await _render_form(request, session, None, values, {}, template="_transaction_form_modal.html")


@router.get("/{transaction_id:int}/edit")
async def edit_transaction_form(request: Request, transaction_id: int,
                                identity: Identity = Depends(page_identity),
                                session: AsyncSession = Depends(get_session)):
    transaction = await _get_transaction_or_404(session, transaction_id, identity)
    values = {
        "stock_id": transaction.stock_id,
        "transaction_date": transaction.transaction_date.isoformat(),
        "type": transaction.type.value,
        "units": f"{transaction.units.normalize():f}",
        "price": f"{transaction.price.normalize():f}",
        "fees": f"{transaction.fees.normalize():f}",
        "notes": transaction.notes or "",
    }
    return await _render_form(request, session, transaction, values, {}, template="_transaction_form_modal.html")


async def _validate(session: AsyncSession, values: dict) -> tuple[TransactionCreate | None, Stock | None, dict]:
    """Form strings → a TransactionCreate with stock_id resolved to a real
    Stock (also returned), or per-field errors."""
    errors: dict[str, list[str]] = {}
    if not values.get("stock_id"):
        errors["stock_id"] = ["Choose a stock."]
    if not values.get("transaction_date"):
        errors["transaction_date"] = ["Enter a date."]
    for field in ("units", "price"):
        if not values.get(field):
            errors[field] = ["This field is required."]
    if errors:
        return None, None, errors

    try:
        transaction_in = TransactionCreate(
            stock_id=values["stock_id"],
            transaction_date=values["transaction_date"],
            type=values.get("type", ""),
            units=values["units"],
            price=values["price"],
            fees=values.get("fees") or 0,
            notes=values.get("notes") or None,
        )
    except ValidationError as exc:
        return None, None, field_errors(exc)

    if transaction_in.units <= 0:
        errors["units"] = ["Must be greater than 0."]
    if transaction_in.price < 0:
        errors["price"] = ["Can't be negative."]
    if (transaction_in.fees or 0) < 0:
        errors["fees"] = ["Can't be negative."]
    stock = await session.get(Stock, int(transaction_in.stock_id)) if str(transaction_in.stock_id).isdigit() else None
    if not stock:
        errors["stock_id"] = ["Choose a stock."]
    if errors or stock is None:
        return None, None, errors
    assert stock.id is not None  # loaded from the database
    transaction_in.stock_id = stock.id
    return transaction_in, stock, {}


def _label(transaction: Transaction | TransactionCreate, stock: Stock) -> str:
    # Callers build this before commit(): with expire_on_commit=True (the
    # test sessions' default) touching attributes afterwards would lazy-load
    # outside the async context.
    return f"{transaction.type.value} {stock.symbol}"


@router.post("")
async def create_transaction(request: Request, identity: Identity = Depends(page_identity),
                             session: AsyncSession = Depends(get_session)):
    form = await request.form()
    values = {field: form.get(field, "") for field in FORM_FIELDS}
    transaction_in, stock, errors = await _validate(session, values)
    if transaction_in is None or stock is None:
        return await _render_form(request, session, None, values, errors, template="_transaction_form.html",
                                  status_code=422)

    transaction = Transaction(**transaction_in.model_dump(), user_id=identity.subject)
    label = _label(transaction, stock)
    session.add(transaction)
    await session.commit()
    return hx_response(f"Added {label}", title="Transaction added", events=(CLOSE_MODAL, CHANGED))


@router.post("/{transaction_id:int}")
async def update_transaction(request: Request, transaction_id: int,
                             identity: Identity = Depends(page_identity),
                             session: AsyncSession = Depends(get_session)):
    transaction = await _get_transaction_or_404(session, transaction_id, identity)
    form = await request.form()
    values = {field: form.get(field, "") for field in FORM_FIELDS}
    transaction_in, stock, errors = await _validate(session, values)
    if transaction_in is None or stock is None:
        return await _render_form(request, session, transaction, values, errors, template="_transaction_form.html",
                                  status_code=422)

    for key, value in transaction_in.model_dump().items():
        setattr(transaction, key, value)
    transaction.recompute()
    transaction.write_datetime = datetime.now(timezone.utc)
    label = _label(transaction, stock)
    session.add(transaction)
    await session.commit()
    return hx_response(f"Saved {label}", title="Transaction saved", events=(CLOSE_MODAL, CHANGED))


@router.post("/bulk-delete")
async def bulk_delete_transactions(request: Request, identity: Identity = Depends(page_identity),
                                   session: AsyncSession = Depends(get_session)):
    """Delete the checked rows (gth_data_table's bulk bar posts them as
    repeated `ids`). Scoped to the signed-in user in the query itself, so
    another user's ids are silently ignored, as the single delete 404s them."""
    ids = [int(v) for v in (await request.form()).getlist("ids") if isinstance(v, str) and v.isdigit()]
    deleted = 0
    if ids:
        result = await session.exec(delete(Transaction).where(
            col(Transaction.user_id) == identity.subject, col(Transaction.id).in_(ids)))
        deleted = result.rowcount
        await session.commit()
    if not deleted:
        return hx_response("No transactions to delete.", "info", events=(CHANGED,))
    noun = "transaction" if deleted == 1 else "transactions"
    return hx_response(f"Deleted {deleted} {noun}", title="Transactions deleted", events=(CHANGED,))


@router.get("/{transaction_id:int}/delete")
async def delete_transaction_confirm(request: Request, transaction_id: int,
                                     identity: Identity = Depends(page_identity),
                                     session: AsyncSession = Depends(get_session)):
    transaction = await _get_transaction_or_404(session, transaction_id, identity)
    return templates.TemplateResponse(request, "_transaction_delete_modal.html", {"transaction": transaction})


@router.delete("/{transaction_id:int}")
async def delete_transaction(transaction_id: int, identity: Identity = Depends(page_identity),
                             session: AsyncSession = Depends(get_session)):
    transaction = await _get_transaction_or_404(session, transaction_id, identity)
    label = _label(transaction, transaction.stock)
    await session.delete(transaction)
    await session.commit()
    return hx_response(f"Deleted {label}", title="Transaction deleted", events=(CHANGED,))
