from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from greentechhub_core.identity import Identity
from greentechhub_fastapi.auth import get_current_user as get_current_identity

from ..templating import templates

router = APIRouter()


@router.get("/")
async def dashboard(request: Request, identity: Identity | None = Depends(get_current_identity)):
    if identity is None:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "dashboard.html", {"identity": identity})
