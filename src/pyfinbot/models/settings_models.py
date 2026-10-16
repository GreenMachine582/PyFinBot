"""greentechhub-core's tables, defined on SQLModel.metadata so Alembic
migrates them with ours: gth_settings (per-user preferences and app
settings), gth_role_grants (roles assigned at /admin/roles) and
gth_login_attempts (failed sign-ins, for the login throttle), gth_audit_log
(the audit log at /admin/audit), gth_api_tokens (personal API tokens,
created at /settings › API tokens) and gth_notifications (the in-app notices
behind the navbar bell)."""

from greentechhub_core.sqlalchemy import (
    api_tokens_table,
    audit_log_table,
    login_attempts_table,
    notifications_table,
    role_grants_table,
    settings_table,
)
from sqlmodel import SQLModel

SETTINGS_TABLE = settings_table(SQLModel.metadata)
ROLE_GRANTS_TABLE = role_grants_table(SQLModel.metadata)
LOGIN_ATTEMPTS_TABLE = login_attempts_table(SQLModel.metadata)
AUDIT_LOG_TABLE = audit_log_table(SQLModel.metadata)
API_TOKENS_TABLE = api_tokens_table(SQLModel.metadata)
NOTIFICATIONS_TABLE = notifications_table(SQLModel.metadata)
