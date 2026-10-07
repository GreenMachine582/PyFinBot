import hashlib

import greentechhub_ui
from fastapi import APIRouter, Depends, Request
from greentechhub_core.identity import Identity
from greentechhub_fastapi.settings import get_settings_service
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.commsec_import import EmailSyncError, sync_commsec_emails
from ...core.email_accounts import load_email_account
from ...core.email_sync import EmailAccount
from ...core.market_sync import sync_guard
from ...db.session import get_session
from ..deps import page_identity
from ..htmx import hx_response
from ..routes.transactions import CHANGED as TRANSACTIONS_CHANGED
from ..templating import templates

router = APIRouter(prefix="/emails")

TITLE = "Email sync finished"
SETTINGS_URL = "/settings#gth-settings-preferences"


def email_sync_lock(subject: str) -> str:
    """The sync lock for one user: each syncs their own mailbox, so users
    don't block each other. Hashed, since the name becomes a lock file."""
    return "commsec-email-sync-" + hashlib.sha256(subject.encode()).hexdigest()[:16]


@router.get("")
async def emails_page(request: Request, identity: Identity = Depends(page_identity)):
    try:
        account = await load_email_account(get_settings_service(request), identity.subject)
        problem = None
    except EmailSyncError as exc:  # a saved password that no longer decrypts
        account, problem = EmailAccount(), exc.message
    return templates.TemplateResponse(request, "emails.html", {
        "configured": account.configured,
        "problem": problem,
        "sender": account.commsec_sender,
        "settings_url": SETTINGS_URL,
    })


@router.post("/sync")
async def sync(request: Request, session: AsyncSession = Depends(get_session),
               identity: Identity = Depends(page_identity)):
    """Runs the sync and swaps the result panel in, with a summary toast."""
    with sync_guard(email_sync_lock(identity.subject)) as acquired:
        if not acquired:
            return hx_response("An email sync is already running — wait for it to finish.", "warning")
        try:
            account = await load_email_account(get_settings_service(request), identity.subject)
            summary = await sync_commsec_emails(session, identity.subject, account)
        except EmailSyncError as exc:
            return templates.TemplateResponse(
                request, "_sync_result.html", {
                    "heading": "Email sync failed", "error": exc.message,
                    # 503: the account isn't set up, or its password needs re-entering
                    "settings_url": SETTINGS_URL if exc.status_code == 503 else None,
                },
                status_code=422,  # swapped in like a gth-form error
                headers={"HX-Trigger": greentechhub_ui.toast(exc.message, "danger", title="Email sync failed")},
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
