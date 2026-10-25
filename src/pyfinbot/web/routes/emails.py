import greentechhub_ui
from fastapi import APIRouter, Depends, Request
from greentechhub_core.background import held_lock, lock_name
from greentechhub_core.identity import Identity
from greentechhub_fastapi.settings import get_settings_service
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core import audit_events
from ...core.commsec_import import EmailSyncError, sync_commsec_emails
from ...core.email_accounts import load_email_account
from ...core.email_sync import EmailAccount
from ...core.market_sync import SYNC_LOCK_TTL_SECONDS
from ...core.settings import settings
from ...db.session import get_session
from ..deps import page_identity, page_router_deps
from ..htmx import hx_response
from ..routes.transactions import CHANGED as TRANSACTIONS_CHANGED
from ..templating import templates

router = APIRouter(prefix="/emails", dependencies=page_router_deps)

TITLE = "Email sync finished"
SETTINGS_URL = "/settings#gth-settings-preferences"


# The sync lock is per user (each syncs their own mailbox, so users don't
# block each other): lock_name hashes the subject into a filename-safe name.
EMAIL_SYNC_LOCK = "commsec-email-sync"


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
    """Runs the sync and swaps the result panel in, with a summary toast.
    The "include_seen" checkbox also reprocesses emails already marked read."""
    include_seen = bool((await request.form()).get("include_seen"))
    with held_lock(settings, lock_name(EMAIL_SYNC_LOCK, identity.subject),
                   ttl=SYNC_LOCK_TTL_SECONDS) as acquired:
        if not acquired:
            return hx_response("An email sync is already running — wait for it to finish.", "warning")
        try:
            account = await load_email_account(get_settings_service(request), identity.subject)
            summary = await sync_commsec_emails(session, identity.subject, account, include_seen=include_seen)
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

    await audit_events.emails_synced(request, summary, recipient=identity.subject)
    imported = greentechhub_ui.pluralise(summary.created, "transaction")
    if not summary.total_emails:
        kind, message = "info", "No new Commsec emails."
    elif not summary.skipped:
        kind, message = "success", f"Imported {imported}."
    else:
        kind, message = "warning", f"Imported {imported}; {summary.skipped} skipped."
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
