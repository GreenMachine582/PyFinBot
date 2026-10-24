"""The migrations: one baseline revision creates every table the models
define (PyFinBot's and greentechhub-core's, gth_users included), matches
them exactly (alembic check finds nothing to add), and downgrades to an
empty database."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from sqlmodel import SQLModel

from pyfinbot import models  # noqa: F401  # registers the tables on SQLModel.metadata

ROOT = Path(__file__).resolve().parents[1]


def _alembic(db: Path, *args: str) -> subprocess.CompletedProcess:
    # A subprocess: alembic's env.py imports the models as src.pyfinbot,
    # which would redefine this process's tables.
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db}",
           "ASYNC_DATABASE_URL": f"sqlite+aiosqlite:///{db}"}
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env,
                          capture_output=True, text=True)


def _tables(db: Path) -> set[str]:
    with sqlite3.connect(db) as conn:
        return {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}


def test_the_baseline_creates_every_table_and_drops_them(tmp_path):
    db = tmp_path / "migrate.db"
    assert _alembic(db, "upgrade", "head").returncode == 0
    assert set(SQLModel.metadata.tables) <= _tables(db)
    with sqlite3.connect(db) as conn:
        columns = [r[1] for r in conn.execute("pragma table_info(gth_users)")]
        fks = {(r[2], r[3], r[4]) for r in conn.execute("pragma foreign_key_list('transaction')")}
    assert columns[:3] == ["id", "username", "email"]
    assert ("gth_users", "user_id", "id") in fks
    check = _alembic(db, "check")
    assert check.returncode == 0, check.stdout + check.stderr
    assert _alembic(db, "downgrade", "base").returncode == 0
    assert _tables(db) <= {"alembic_version"}
