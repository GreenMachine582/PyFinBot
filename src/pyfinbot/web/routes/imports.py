import greentechhub_ui
from fastapi import APIRouter, Depends, File, Request, UploadFile
from greentechhub_core.identity import Identity
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.transaction_import import (
    ACCEPTED_EXTENSIONS,
    COLUMN_ALIASES,
    REQUIRED_COLUMNS,
    ImportFileError,
    import_transactions,
)
from ...db.session import get_session
from ..deps import page_identity
from ..routes.transactions import CHANGED as TRANSACTIONS_CHANGED
from ..templating import templates

router = APIRouter(prefix="/import")

TITLE = "Import finished"


@router.get("")
async def import_page(request: Request, identity: Identity = Depends(page_identity)):
    return templates.TemplateResponse(request, "import.html", {
        "accept": ",".join(ACCEPTED_EXTENSIONS),
        "columns": COLUMN_ALIASES,
        "required": REQUIRED_COLUMNS,
    })


def _plural(n: int) -> str:
    return f"{n} transaction" if n == 1 else f"{n} transactions"


@router.post("")
async def upload(request: Request, file: UploadFile | None = File(None),
                 session: AsyncSession = Depends(get_session), identity: Identity = Depends(page_identity)):
    """Runs the import and swaps the result panel in, with a summary toast."""
    # Optional so a submit with no file chosen gets the "empty file" message
    # below rather than FastAPI's JSON 422 swapped into the page.
    filename = file.filename if file else ""
    try:
        content = await file.read() if file else b""
        summary = await import_transactions(session, identity.subject, content, filename or "")
    except ImportFileError as exc:
        return templates.TemplateResponse(
            request, "_import_result.html", {"error": exc.detail, "filename": filename},
            status_code=422,  # swapped in like a gth-form error
            headers={"HX-Trigger": greentechhub_ui.toast(exc.detail, "danger", title="Import failed")},
        )

    if not summary.total_rows:
        kind, message = "info", "The file has no rows to import."
    elif not summary.skipped:
        kind, message = "success", f"Imported {_plural(summary.created)}."
    elif summary.created:
        kind, message = "warning", f"Imported {_plural(summary.created)}; {summary.skipped} skipped."
    else:
        kind, message = "warning", f"Nothing imported; {summary.skipped} skipped."
    trigger = greentechhub_ui.toast(message, kind, title=TITLE,
                                    events=(TRANSACTIONS_CHANGED,) if summary.created else ())
    return templates.TemplateResponse(
        request, "_import_result.html", {"summary": summary, "filename": filename},
        headers={"HX-Trigger": trigger},
    )
