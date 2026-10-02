from __future__ import annotations

from contextlib import asynccontextmanager

import importlib
import pkgutil

import greentechhub_ui
from fastapi import FastAPI
from fastapi_pagination import add_pagination
from greentechhub_core.settings.crypto import FernetCipher
from greentechhub_core.sqlalchemy import SQLAlchemyGrantStore, SQLAlchemySettingsStore
from greentechhub_fastapi import (
    register_auth,
    register_core,
    register_permissions,
    register_settings,
)
from greentechhub_fastapi.permissions import RoleAdminViews
from greentechhub_fastapi.settings import SettingsViews
from greentechhub_fastapi.templating import mount_static_dirs

from . import version, api
from .core.permissions import ROLES, SETTINGS_MANAGE, USERS_MANAGE
from .core.settings import settings, settings_cipher_key
from .core.user_settings import USER_SETTINGS
from .db.session import init_db, session_factory
from .models.settings_models import ROLE_GRANTS_TABLE, SETTINGS_TABLE
from .web.templating import templates
from .web.routes import (
    auth as web_auth,
    dashboard as web_dashboard,
    dividends as web_dividends,
    emails as web_emails,
    reports as web_reports,
    imports as web_imports,
    stocks as web_stocks,
    transactions as web_transactions,
)


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

# Roles: the admin role (core/permissions.py) comes from ROLE_BOOTSTRAP /
# ROLE_GROUPS or a grant made at /admin/roles (gth_role_grants). Before
# register_settings, which gates Settings › App on SETTINGS_MANAGE.
register_permissions(
    app,
    settings,
    roles=ROLES,
    grants=SQLAlchemyGrantStore(ROLE_GRANTS_TABLE, async_session_factory=session_factory),
)

# Per-user preferences and app settings (greentechhub-core settings in the
# gth_settings table): /settings (its App section for SETTINGS_MANAGE), the
# navbar user menu (Settings, Log out), the server-saved theme, and
# user_settings for the date/money/number filters and table page sizes.
register_settings(
    app,
    settings,
    registry=USER_SETTINGS,
    store=SQLAlchemySettingsStore(SETTINGS_TABLE, async_session_factory=session_factory),
    views=SettingsViews(templates=templates),
    manage_permission=SETTINGS_MANAGE,
    logout_url="/logout",
    # Encrypts secret settings (each user's email app password) at rest.
    cipher=FernetCipher(settings_cipher_key()),
)

# greentechhub-ui static assets its templates reference.
mount_static_dirs(app, greentechhub_ui.static_dirs())

# web_auth's login/logout routes are local-auth-only (see its own
# build_router() docstring) — None under any other AUTH_ADAPTER.
web_auth_router = web_auth.build_router()
if web_auth_router is not None:
    app.include_router(web_auth_router)
app.include_router(web_dashboard.router)
# /admin/roles: assign roles to users (USERS_MANAGE).
app.include_router(RoleAdminViews(templates=templates, permission=USERS_MANAGE).router())
app.include_router(web_stocks.router)
app.include_router(web_transactions.router)
app.include_router(web_imports.router)
app.include_router(web_emails.router)
app.include_router(web_dividends.router)
app.include_router(web_reports.router)

# Register all routers

# Loop through all modules in the routes package
for _, module_name, _ in pkgutil.iter_modules(api.__path__):
    module = importlib.import_module(f"{api.__name__}.{module_name}")
    if hasattr(module, "router"):
        app.include_router(module.router, prefix="/api")


# Enable pagination for all routes
add_pagination(app)
