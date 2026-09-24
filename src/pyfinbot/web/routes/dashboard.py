from fastapi import APIRouter, Depends, Request
from greentechhub_core.identity import Identity

from ..deps import page_identity
from ..templating import templates

router = APIRouter()


@router.get("/")
async def dashboard(request: Request, identity: Identity = Depends(page_identity)):
    return templates.TemplateResponse(request, "dashboard.html", {"identity": identity})
