import greentechhub_ui
from fastapi import APIRouter, Depends, Request
from greentechhub_core.identity import Identity
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.commsec_import import EmailSyncError, sync_commsec_emails
from ...core.market_sync import sync_guard
from ...core.settings import settings
from ...db.session import get_session
from ..deps import page_identity
from ..htmx import hx_response
from ..routes.transactions import CHANGED as TRANSACTIONS_CHANGED
from ..templating import templates

router = APIRouter(prefix="/emails")

# One Gmail mailbox backs every sync, so one lock for all users.
LOCK = "commsec-email-sync"
TITLE = "Email sync finished"


@router.get("")
async def emails_page(request: Request, identity: Identity = Depends(page_identity)):
    return templates.TemplateResponse(request, "emails.html", {
        "configured": bool(settings.GMAIL_ADDRESS and settings.GMAIL_APP_PASSWORD),
        "sender": settings.COMMSEC_SENDER,
    })


@router.post("/sync")
async def sync(request: Request, session: AsyncSession = Depends(get_session),
               identity: Identity = Depends(page_identity)):
    """Runs the sync and swaps the result panel in, with a summary toast."""
    with sync_guard(LOCK) as acquired:
        if not acquired:
            return hx_response("An email sync is already running — wait for it to finish.", "warning")
        try:
            summary = await sync_commsec_emails(session, identity.subject)
        except EmailSyncError as exc:
            return templates.TemplateResponse(
                request, "_sync_result.html", {"heading": "Email sync failed", "error": exc.detail},
                status_code=422,  # swapped in like a gth-form error
                headers={"HX-Trigger": greentechhub_ui.toast(exc.detail, "danger", title="Email sync failed")},
            )

    noun = "transaction" if summary.created == 1 else "transactions"
    if not summary.total_emails:
        kind, message = "info", "No new Commsec emails."
    elif not summary.skipped:
        kind, message = "success", f"Imported {summary.created} {noun}."
    else:
        kind, message = "warning", f"Imported {summary.created} {noun}; {summary.skipped} skipped."
    trigger = greentechhub_ui.toast(message, kind, title=TITLE,
                                    events=(TRANSACTIONS_CHANGED,) if summary.created else ())
    return templates.TemplateResponse(request, "_sync_result.html", {
        "heading": "Email sync results",
        "badges": [
            (f"{summary.total_emails} emails", "neutral"),
            (f"{summary.created} imported", "good" if summary.created else "neutral"),
            (f"{summary.skipped} skipped", "warn" if summary.skipped else "neutral"),
        ],
        "problems": summary.errors,
        "link": ("/transactions", "View transactions") if summary.created else None,
    }, headers={"HX-Trigger": trigger})
