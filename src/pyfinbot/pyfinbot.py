from __future__ import annotations

from contextlib import asynccontextmanager

import importlib
import pkgutil

import greentechhub_ui
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi_pagination import add_pagination
from greentechhub_fastapi import register_auth, register_core

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

# CORS: development allows all origins when CORS_ALLOWED_ORIGINS is unset
# (frictionless local/Swagger testing); production allows none until
# CORS_ALLOWED_ORIGINS is set. register_core's own CORS wiring has no such
# dev-friendly default (empty means empty), so it's applied here, before
# calling it, the same way this dev-default logic always has.
if settings.ENVIRONMENT == "development" and not settings.CORS_ALLOWED_ORIGINS:
    settings.CORS_ALLOWED_ORIGINS = "*"

# request-id/timing/security-header/CORS/trusted-proxy middleware, and
# session-cookie auth (AUTH_ADAPTER=local for now — see
# web-implementation-brief.md for the later forward_auth/Authentik swap).
# register_core before register_auth: forward_auth's trust gate depends on
# register_core's ProxyHeadersMiddleware having already run (see
# greentechhub-fastapi's docs/auth.md) — not load-bearing for AUTH_ADAPTER=
# local today, but the right order to not need revisiting later.
register_core(app, settings)
register_auth(app, settings)

# greentechhub-ui static assets its templates reference.
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
