"""greentechhub-core's tables, defined on SQLModel.metadata so Alembic
migrates them with ours: gth_settings (per-user preferences and app
settings) and gth_role_grants (roles assigned at /admin/roles)."""

from greentechhub_core.sqlalchemy import role_grants_table, settings_table
from sqlmodel import SQLModel

SETTINGS_TABLE = settings_table(SQLModel.metadata)
ROLE_GRANTS_TABLE = role_grants_table(SQLModel.metadata)
