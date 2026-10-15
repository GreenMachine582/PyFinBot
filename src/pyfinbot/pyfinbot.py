from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import importlib
import pkgutil

import greentechhub_ui
from fastapi import Depends, FastAPI
from greentechhub_core.settings.crypto import settings_cipher
from greentechhub_core.sqlalchemy import SQLAlchemyAuditStore, SQLAlchemyGrantStore, SQLAlchemySettingsStore
from greentechhub_fastapi import (
    register_admin,
    register_audit,
    register_auth,
    register_core,
    register_csp,
    register_csrf,
    register_health,
    register_logging,
    register_permissions,
    register_settings,
)
from greentechhub_fastapi.auth import bearer_scheme
from greentechhub_fastapi.exceptions import register_api_error_handlers, register_exception_handlers
from greentechhub_fastapi.settings import SettingsViews
from greentechhub_fastapi.templating import mount_static_dirs

from . import version, api
from .core.login_throttle import LOGIN_THROTTLE
from .core.permissions import ROLES, SETTINGS_MANAGE
from .core.settings import settings
from .core.user_settings import USER_SETTINGS
from .db.session import database_ready, init_db, session_factory
from .models.settings_models import AUDIT_LOG_TABLE, ROLE_GRANTS_TABLE, SETTINGS_TABLE
from .web.templating import ADMIN_VIEWS, AUDIT_VIEWS, templates
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


def csp_frame_src(config) -> list[str]:
    """The origins the CSP's frame-src allows beyond 'self': the Grafana origin
    for the dashboard's embedded panels, when GRAFANA_ORIGIN is set."""
    return [config.GRAFANA_ORIGIN] if config.GRAFANA_ORIGIN else []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager to initialise the database on startup.
    """
    await init_db()
    # Nothing else deletes old gth_login_attempts rows; once a start is enough.
    await LOGIN_THROTTLE.prune()
    await prune_audit_log()
    yield


async def prune_audit_log(now: datetime | None = None) -> int:
    """Delete gth_audit_log entries older than AUDIT_RETENTION_DAYS (none when
    it's 0) and return how many went. Run on startup: entries pile up slowly
    at personal-use scale, so once a start is enough."""
    if settings.AUDIT_RETENTION_DAYS <= 0:
        return 0
    before = (now or datetime.now(UTC)) - timedelta(days=settings.AUDIT_RETENTION_DAYS)
    return await AUDIT_STORE.prune(before)


app = FastAPI(
    lifespan=lifespan,
    title=version.PROJECT_NAME_TEXT,
    description=version.DESCRIPTION,
    version=version.VERSION
)

# Structured logs: one JSON object per line on stdout (greentechhub-core),
# tagged with the service and version, at LOG_LEVEL; uvicorn's own loggers go
# through the same JSON handler, so every line is JSON.
register_logging(app, settings, service="pyfinbot", version=version.VERSION, uvicorn=True)

# /api errors as greentechhub's {code, message, details} envelope: core's
# ApplicationError hierarchy (at its status_code hint when it has one, e.g. a
# 502 sync failure), plus framework errors and the OAuth2 401 challenge under
# /api; pages keep FastAPI's defaults.
register_exception_handlers(app)
register_api_error_handlers(app, prefix="/api")

# /health (liveness) and /health/ready (SELECT 1 against the database).
register_health(app, checks=[database_ready])

# request-id/timing/security-header/CORS/trusted-proxy middleware, and
# session-cookie auth (AUTH_ADAPTER=local for now — see
# web-implementation-brief.md for the later forward_auth/Authentik swap).
# register_core before register_auth: forward_auth's trust gate depends on
# register_core's ProxyHeadersMiddleware having already run (see
# greentechhub-fastapi's docs/auth.md) — not load-bearing for AUTH_ADAPTER=
# local today, but the right order to not need revisiting later.
register_core(app, settings)
# bearer=True: the API also takes `Authorization: Bearer` tokens (issue_token
# in api/auth_routes.py), through the same get_current_user as pages.
register_auth(app, settings, bearer=True)
# A strict Content-Security-Policy with a fresh nonce per request: greentechhub-
# ui's shell puts it on every <script> (templates get it as csp_nonce through
# ui_context), so only our own scripts run. After register_core, so the nonce
# also reaches the 500 page. frame-src adds the Grafana origin for the
# dashboard's embedded panels when GRAFANA_ORIGIN is set.
register_csp(app, settings, frame_src=csp_frame_src(settings))
# A CSRF token for every request (the gth_csrf cookie; templates get it as
# csrf_token). The page routers (web/deps.py page_router_deps), settings,
# roles and logout check it.
register_csrf(app)

# The audit log (gth_audit_log), read by admins at /admin/audit. fastapi's
# views record sign-ins, lockouts, password, role and settings changes into
# it; PyFinBot's syncs and imports add theirs (core/audit_events.py).
AUDIT_STORE = SQLAlchemyAuditStore(AUDIT_LOG_TABLE, async_session_factory=session_factory)
register_audit(app, settings, store=AUDIT_STORE, views=AUDIT_VIEWS)

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
    views=SettingsViews(templates=templates, change_password=web_auth.change_password, csrf=True),
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
# The admin pages (web/templating.py ADMIN_VIEWS, under the nav's "Admin"
# group): /admin/roles assigns roles (USERS_MANAGE); /admin/audit, already
# mounted by register_audit above, isn't mounted twice.
register_admin(app, settings, views=ADMIN_VIEWS)
app.include_router(web_stocks.router)
app.include_router(web_transactions.router)
app.include_router(web_imports.router)
app.include_router(web_emails.router)
app.include_router(web_dividends.router)
app.include_router(web_reports.router)

# Register all routers

# Loop through all modules in the routes package
for module_info in pkgutil.iter_modules(api.__path__):
    module = importlib.import_module(f"{api.__name__}.{module_info.name}")
    if hasattr(module, "router"):
        # bearer_scheme only documents the token flow in OpenAPI (Swagger's
        # Authorize button); get_current_identity does the checking.
        app.include_router(module.router, prefix="/api",
                           dependencies=[Depends(bearer_scheme("/api/auth/login"))])

