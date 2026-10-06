from __future__ import annotations

from contextlib import asynccontextmanager

import importlib
import logging
import pkgutil

import greentechhub_ui
from fastapi import FastAPI
from greentechhub_core.settings.crypto import settings_cipher
from greentechhub_core.sqlalchemy import SQLAlchemyGrantStore, SQLAlchemySettingsStore
from greentechhub_core.logging import configure_logging
from greentechhub_fastapi import (
    register_auth,
    register_core,
    register_health,
    register_permissions,
    register_settings,
)
from greentechhub_fastapi.exceptions import register_api_error_handlers, register_exception_handlers
from greentechhub_fastapi.permissions import RoleAdminViews
from greentechhub_fastapi.settings import SettingsViews
from greentechhub_fastapi.templating import mount_static_dirs

from . import version, api
from .core.login_throttle import LOGIN_THROTTLE
from .core.permissions import ROLES, SETTINGS_MANAGE, USERS_MANAGE
from .core.settings import settings
from .core.user_settings import USER_SETTINGS
from .db.session import database_ready, init_db, session_factory
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
    # Nothing else deletes old gth_login_attempts rows; once a start is enough.
    await LOGIN_THROTTLE.prune()
    yield


# Structured logs: one JSON object per line on stdout (greentechhub-core),
# tagged with the service and version, at LOG_LEVEL. configure_logging
# directly rather than register_logging, which doesn't pass service/version.
configure_logging(settings.log_level, service="pyfinbot", version=version.VERSION)
# Uvicorn sets up its own plain-text loggers before importing the app; send
# them through the root's JSON handler too, so every line is JSON.
for _name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    logging.getLogger(_name).handlers.clear()
    logging.getLogger(_name).propagate = True

app = FastAPI(
    lifespan=lifespan,
    title=version.PROJECT_NAME_TEXT,
    description=version.DESCRIPTION,
    version=version.VERSION
)

# /api errors as greentechhub's {code, message, details} envelope: core's
# ApplicationError hierarchy (at its status_code hint when it has one, e.g. a
# 502 sync failure), plus framework errors and the OAuth2 401 challenge under
# /api; pages keep FastAPI's defaults.
register_exception_handlers(app)
register_api_error_handlers(app, prefix="/api")

# /health (liveness) and /health/ready (SELECT 1 against the database).
register_health(app, checks=[database_ready])

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

# The context PyFinBot derived its cipher key under before core's settings_cipher
# existed: the same key, so saved app passwords stay readable.
CIPHER_CONTEXT = "pyfinbot-settings"

# Per-user preferences and app settings (greentechhub-core settings in the
# gth_settings table): /settings (its App section for SETTINGS_MANAGE), the
# navbar user menu (Settings, Log out), the server-saved theme, a Password
# section (web_auth.change_password), and user_settings for the
# date/money/number filters and table page sizes.
register_settings(
    app,
    settings,
    registry=USER_SETTINGS,
    store=SQLAlchemySettingsStore(SETTINGS_TABLE, async_session_factory=session_factory),
    views=SettingsViews(templates=templates, change_password=web_auth.change_password),
    manage_permission=SETTINGS_MANAGE,
    logout_url="/logout",
    # Encrypts secret settings (each user's email app password) at rest.
    cipher=settings_cipher(settings, context=CIPHER_CONTEXT),
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

