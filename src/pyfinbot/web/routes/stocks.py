import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from greentechhub_fastapi.query import PageParams, next_page_url
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
from ..paging import paginate, web_page_params
from ..templating import templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stocks", dependencies=[Depends(page_identity)])

CHANGED = "stocksChanged"
STATUSES = {"active": "Active", "archived": "Archived", "all": "All"}
SORTS = {
    "market,symbol": "Market, symbol",
    "symbol": "Symbol A–Z",
    "-symbol": "Symbol Z–A",
    "name": "Name A–Z",
}
OPTIONS_LIMIT = 20


async def _get_stock_or_404(session: AsyncSession, stock_id: int) -> Stock:
    stock = await session.get(Stock, stock_id)
    if not stock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    return stock


async def _rows_context(session: AsyncSession, params: PageParams, q: str, market: str,
                        status_: str, sort: str) -> dict:
    stmt = select(Stock)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Stock.symbol.ilike(like), Stock.name.ilike(like)))
    if market:
        stmt = stmt.where(Stock.market == market)
    if status_ == "active":
        stmt = stmt.where(Stock.is_active.is_(True))
    elif status_ == "archived":
        stmt = stmt.where(Stock.is_active.is_(False))
    stmt = stmt.order_by(*buildSortOrderBy(Stock, ALLOWED_FILTERING_FIELDS, None, sort or "market,symbol"))

    page = await paginate(session, stmt, params)
    return {
        "stocks": page.items,
        "total": page.total,
        "next_url": next_page_url("/stocks/rows", page, {"q": q, "market": market, "status": status_, "sort": sort}),
    }


@router.get("")
async def stocks_page(
    request: Request,
    session: AsyncSession = Depends(get_session),
    params: PageParams = Depends(web_page_params),
):
    markets = (await session.exec(select(Stock.market).distinct().order_by(Stock.market))).all()
    context = await _rows_context(session, params, "", "", "active", "market,symbol")
    return templates.TemplateResponse(request, "stocks.html", {
        **context,
        "markets": markets,
        "statuses": STATUSES,
        "sorts": SORTS,
        "sync_markets": sorted(MARKET_FETCHERS),
    })


@router.get("/rows")
async def stock_rows(
    request: Request,
    session: AsyncSession = Depends(get_session),
    params: PageParams = Depends(web_page_params),
    q: str = "",
    market: str = "",
    status_: str = Query("active", alias="status"),
    sort: str = "market,symbol",
):
    context = await _rows_context(session, params, q, market, status_, sort)
    return templates.TemplateResponse(request, "_stock_rows.html", context)


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
    return hx_response(f"Added {market}:{symbol}", events=(CLOSE_MODAL, CHANGED))


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
    return hx_response(f"Saved {label}", events=(CLOSE_MODAL, CHANGED))


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
        return hx_response(f"{label} has {in_use} {noun} — archive it instead.", "danger")

    await session.delete(stock)
    await session.commit()
    return hx_response(f"Deleted {label}", events=(CHANGED,))


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
            return hx_response(f"{market} sync failed — see the server logs.", "danger")
    return hx_response(
        f"{market} sync: {len(created)} created, {len(updated)} updated, {len(archived)} archived",
        events=(CHANGED,),
    )
