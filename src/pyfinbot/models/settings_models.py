"""greentechhub-core's gth_settings table (per-user preferences, later app
settings), defined on SQLModel.metadata so Alembic migrates it with ours."""

from greentechhub_core.sqlalchemy import settings_table
from sqlmodel import SQLModel

SETTINGS_TABLE = settings_table(SQLModel.metadata)
