"""greentechhub-core's tables, defined on SQLModel.metadata so Alembic
migrates them with ours: gth_settings (per-user preferences and app
settings), gth_role_grants (roles assigned at /admin/roles) and
gth_login_attempts (failed sign-ins, for the login throttle)."""

from greentechhub_core.sqlalchemy import login_attempts_table, role_grants_table, settings_table
from sqlmodel import SQLModel

SETTINGS_TABLE = settings_table(SQLModel.metadata)
ROLE_GRANTS_TABLE = role_grants_table(SQLModel.metadata)
LOGIN_ATTEMPTS_TABLE = login_attempts_table(SQLModel.metadata)
