import greentechhub_ui
from fastapi import APIRouter, Depends, Request
from greentechhub_core.identity import Identity
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.dividend_sync import syncDividends, user_stock_ids
from ...core.market_sync import sync_guard
from ...db.session import get_session
from ...models.stock_models import Stock
from ..deps import page_identity
from ..htmx import hx_response
from ..templating import templates

router = APIRouter(prefix="/dividends")

# Dividend rows are shared across users (one per stock + ex-date), so
# concurrent syncs could race on the same upserts — one lock for all.
LOCK = "dividend-sync"
TITLE = "Dividend sync finished"


@router.get("")
async def dividends_page(request: Request, identity: Identity = Depends(page_identity)):
    return templates.TemplateResponse(request, "dividends.html", {})


@router.post("/sync")
async def sync(request: Request, session: AsyncSession = Depends(get_session),
               identity: Identity = Depends(page_identity)):
    """Syncs one picked stock (form field stock_id) or, without one, every
    stock the user has transacted; swaps the result panel in with a toast."""
    stock_id = str((await request.form()).get("stock_id", "")).strip()
    if stock_id:
        stock = await session.get(Stock, int(stock_id)) if stock_id.isdigit() else None
        if not stock:
            return hx_response("Pick a stock from the list first.", "warning")
        target_ids = [int(stock_id)]
        scope = f"{stock.market}:{stock.symbol}"
    else:
        target_ids = await user_stock_ids(session, identity.subject)
        if not target_ids:
            return hx_response("You have no transactions yet, so there are no stocks to sync.", "info")
        scope = f"{len(target_ids)} stock" + ("" if len(target_ids) == 1 else "s")

    with sync_guard(LOCK) as acquired:
        if not acquired:
            return hx_response("A dividend sync is already running — wait for it to finish.", "warning")
        created, updated, errors = await syncDividends(session, stock_ids=target_ids)

    changed = len(created) + len(updated)
    if errors:
        kind = "warning" if changed else "danger"
        message = f"{len(created)} new, {len(updated)} updated; {len(errors)} failed."
    elif changed:
        kind, message = "success", f"{len(created)} new, {len(updated)} updated."
    else:
        kind, message = "info", "Already up to date."
    return templates.TemplateResponse(request, "_sync_result.html", {
        "heading": f"Dividend sync results — {scope}",
        "badges": [
            (f"{len(created)} new", "good" if created else "neutral"),
            (f"{len(updated)} updated", "info" if updated else "neutral"),
            (f"{len(errors)} failed", "bad" if errors else "neutral"),
        ],
        "problems": errors,
    }, headers={"HX-Trigger": greentechhub_ui.toast(message, kind, title=f"{TITLE} — {scope}")})
