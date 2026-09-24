import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from greentechhub_ui import TableState
from greentechhub_ui.htmx import wants_fragment
from sqlalchemy import func, or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ...api.stock_routes import ALLOWED_FILTERING_FIELDS
from ...core.market_sync import MARKET_FETCHERS, market_sync_guard, syncMarket
from ...core.sorting import buildSortOrderBy
from ...db.session import get_session
from ...models.stock_models import Stock
from ...models.transaction_models import Transaction
from ..deps import page_identity
from ..htmx import CLOSE_MODAL, hx_response
from ..paging import PAGE_SIZE, PAGE_SIZES, paginate, sort_string
from ..templating import templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stocks", dependencies=[Depends(page_identity)])

CHANGED = "stocksChanged"
STATUSES = {"active": "Active", "archived": "Archived", "all": "All"}
OPTIONS_LIMIT = 20


async def _get_stock_or_404(session: AsyncSession, stock_id: int) -> Stock:
    stock = await session.get(Stock, stock_id)
    if not stock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    return stock


def _table_state(request: Request) -> TableState:
    return TableState.from_query(
        request.query_params,
        id="stocks",
        base_url="/stocks",
        page_size=PAGE_SIZE,
        page_sizes=PAGE_SIZES,
        sortable=("symbol", "market", "name"),
        default_sort="market",
        filter_params=("q", "market", "status"),
    )


async def _query_stocks(session: AsyncSession, state: TableState) -> tuple[list[Stock], TableState]:
    stmt = select(Stock)
    if q := state.filters.get("q"):
        like = f"%{q}%"
        stmt = stmt.where(or_(Stock.symbol.ilike(like), Stock.name.ilike(like)))
    if market := state.filters.get("market"):
        stmt = stmt.where(Stock.market == market)
    status_ = state.filters.get("status", "active")
    if status_ == "active":
        stmt = stmt.where(Stock.is_active.is_(True))
    elif status_ == "archived":
        stmt = stmt.where(Stock.is_active.is_(False))
    sort = sort_string(state, "market", "symbol", "id")
    stmt = stmt.order_by(*buildSortOrderBy(Stock, ALLOWED_FILTERING_FIELDS, None, sort))
    return await paginate(session, stmt, state)


@router.get("")
async def stocks_page(request: Request, session: AsyncSession = Depends(get_session)):
    """The page, or (htmx: sort, filter, load more, refresh) just the table."""
    stocks, state = await _query_stocks(session, _table_state(request))
    context = {"table": state, "stocks": stocks}
    if wants_fragment(request.headers):
        return templates.TemplateResponse(request, "_stock_table.html", context)
    markets = (await session.exec(select(Stock.market).distinct().order_by(Stock.market))).all()
    return templates.TemplateResponse(request, "stocks.html", {
        **context,
        "markets": markets,
        "statuses": STATUSES,
        "sync_markets": sorted(MARKET_FETCHERS),
    })


@router.get("/options")
async def stock_options(request: Request, session: AsyncSession = Depends(get_session), q: str = ""):
    """Result rows for the transaction form's stock-picker combobox."""
    stmt = select(Stock).where(Stock.is_active.is_(True))
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Stock.symbol.ilike(like), Stock.name.ilike(like)))
    stmt = stmt.order_by(Stock.symbol, Stock.market).limit(OPTIONS_LIMIT)
    stocks = (await session.exec(stmt)).all()
    return templates.TemplateResponse(request, "_stock_options.html", {"stocks": stocks})


@router.get("/new")
async def new_stock_form(request: Request):
    return templates.TemplateResponse(request, "_stock_form_modal.html", {"stock": None, "values": {}, "errors": {}})


@router.get("/{stock_id:int}/edit")
async def edit_stock_form(request: Request, stock_id: int, session: AsyncSession = Depends(get_session)):
    stock = await _get_stock_or_404(session, stock_id)
    values = {"name": stock.name, "is_active": stock.is_active}
    return templates.TemplateResponse(request, "_stock_form_modal.html", {"stock": stock, "values": values, "errors": {}})


def _form_error(request: Request, stock: Stock | None, values: dict, errors: dict):
    return templates.TemplateResponse(
        request, "_stock_form.html", {"stock": stock, "values": values, "errors": errors},
        status_code=422,
    )


@router.post("")
async def create_stock(request: Request, session: AsyncSession = Depends(get_session)):
    values = {field: str(form_value) for field, form_value in (await request.form()).items()}
    market = values.get("market", "").strip().upper()
    symbol = values.get("symbol", "").strip().upper()
    name = values.get("name", "").strip()
    errors = {f: ["This field is required."] for f, v in (("market", market), ("symbol", symbol), ("name", name)) if not v}
    if not errors and await Stock.search(session, market=market, symbol=symbol):
        errors["symbol"] = [f"{market}:{symbol} already exists."]
    if errors:
        return _form_error(request, None, values, errors)

    session.add(Stock(market=market, symbol=symbol, name=name))
    await session.commit()
    return hx_response(f"Added {market}:{symbol}", title="Stock added", events=(CLOSE_MODAL, CHANGED))


@router.post("/{stock_id:int}")
async def update_stock(request: Request, stock_id: int, session: AsyncSession = Depends(get_session)):
    stock = await _get_stock_or_404(session, stock_id)
    form = await request.form()
    values = {"name": str(form.get("name", "")), "is_active": form.get("is_active") == "on"}
    if not values["name"].strip():
        return _form_error(request, stock, values, {"name": ["This field is required."]})

    stock.name = values["name"].strip()
    stock.is_active = values["is_active"]
    # Mirrors the API's archive stamp, and also clears it on reactivation
    # so archived_at never lingers on an active stock.
    stock.archived_at = None if stock.is_active else (stock.archived_at or datetime.now(timezone.utc))
    stock.write_datetime = datetime.now(timezone.utc)
    label = f"{stock.market}:{stock.symbol}"
    session.add(stock)
    await session.commit()
    return hx_response(f"Saved {label}", title="Stock saved", events=(CLOSE_MODAL, CHANGED))


@router.get("/{stock_id:int}/delete")
async def delete_stock_confirm(request: Request, stock_id: int, session: AsyncSession = Depends(get_session)):
    stock = await _get_stock_or_404(session, stock_id)
    return templates.TemplateResponse(request, "_stock_delete_modal.html", {"stock": stock})


@router.delete("/{stock_id:int}")
async def delete_stock(stock_id: int, session: AsyncSession = Depends(get_session)):
    stock = await _get_stock_or_404(session, stock_id)
    label = f"{stock.market}:{stock.symbol}"
    # Transaction.stock_id has no cascade — deleting a referenced stock would
    # fail on the FK, so refuse up front and point at archiving instead.
    in_use = (await session.exec(
        select(func.count()).select_from(Transaction).where(Transaction.stock_id == stock.id)
    )).one()
    if in_use:
        noun = "transaction" if in_use == 1 else "transactions"
        return hx_response(f"{label} has {in_use} {noun} — archive it instead.", "danger", title="Can't delete")

    await session.delete(stock)
    await session.commit()
    return hx_response(f"Deleted {label}", title="Stock deleted", events=(CHANGED,))


@router.post("/sync/{market}")
async def sync_market(market: str, session: AsyncSession = Depends(get_session)):
    market = market.upper()
    if market not in MARKET_FETCHERS:
        return hx_response(f"Sync for market '{market}' is not supported.", "danger")

    with market_sync_guard(market) as acquired:
        if not acquired:
            return hx_response(f"{market} sync is already running — wait for it to finish.", "warning")
        try:
            created, updated, archived = await syncMarket(session, market)
        except Exception:  # network/parse failures: log the detail, toast a summary
            logger.exception("%s market sync failed", market)
            return hx_response(f"{market} sync failed — see the server logs.", "danger", title="Sync failed")
    changed = len(created) + len(updated) + len(archived)
    return hx_response(
        f"{len(created)} created, {len(updated)} updated, {len(archived)} archived",
        "success" if changed else "info",
        title=f"{market} sync complete",
        events=(CHANGED,),
    )
