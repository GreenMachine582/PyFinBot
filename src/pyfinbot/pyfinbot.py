from __future__ import annotations

from contextlib import asynccontextmanager

import importlib
import pkgutil

import greentechhub_ui
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi_pagination import add_pagination
from greentechhub_fastapi import register_auth

from . import version, api
from .core.settings import settings
from .db.session import init_db
from .web.routes import auth as web_auth, dashboard as web_dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager to initialise the database on startup.
    """
    await init_db()
    yield


app = FastAPI(
    lifespan=lifespan,
    title=version.PROJECT_NAME_TEXT,
    description=version.DESCRIPTION,
    version=version.VERSION
)

# CORS: development allows all origins when CORS_ORIGINS is unset (frictionless
# local/Swagger testing); production allows none until CORS_ORIGINS is set.
_cors_origins = settings.cors_origins_list
if settings.ENVIRONMENT == "development" and not _cors_origins:
    _cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Web UI: session-cookie auth (AUTH_ADAPTER=local for now — see
# web-implementation-brief.md for the later forward_auth/Authentik swap) and
# the greentechhub-ui static assets its templates reference.
register_auth(app, settings)
app.mount("/gth-static", StaticFiles(directory=greentechhub_ui.theme_path), name="gth-static")
app.mount("/gth-assets", StaticFiles(directory=greentechhub_ui.static_path), name="gth-assets")

# web_auth's login/logout routes are local-auth-only (see its own
# build_router() docstring) — None under any other AUTH_ADAPTER.
web_auth_router = web_auth.build_router()
if web_auth_router is not None:
    app.include_router(web_auth_router)
app.include_router(web_dashboard.router)

# Register all routers

# Loop through all modules in the routes package
for _, module_name, _ in pkgutil.iter_modules(api.__path__):
    module = importlib.import_module(f"{api.__name__}.{module_name}")
    if hasattr(module, "router"):
        app.include_router(module.router, prefix="/api")


# Enable pagination for all routes
add_pagination(app)
