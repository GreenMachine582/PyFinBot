"""Service basics from greentechhub-core's GTHBaseSettings (v0.13): the
ephemeral SECRET_KEY, ENVIRONMENT, the development CORS default and the
FileLock directory are core's fields and opt-ins, not PyFinBot's own."""
import tempfile
from pathlib import Path

import pytest

from pyfinbot.core import market_sync

from .test_settings import _settings_module


def _settings(monkeypatch, **env):
    for name in ("SECRET_KEY", "ENVIRONMENT", "CORS_ALLOWED_ORIGINS", "LOCK_DIR"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return _settings_module().Settings(_env_file=None)


def test_pyfinbots_own_copies_are_gone():
    fields = _settings_module().Settings.model_fields
    assert "ENVIRONMENT" not in fields and "LOCK_DIR" not in fields
    assert {"environment", "lock_dir", "secret_key"} <= set(fields)


def test_unset_secret_key_is_random_per_instance_with_a_warning(monkeypatch):
    with pytest.warns(UserWarning, match="SECRET_KEY is not set"):
        first = _settings(monkeypatch)
    with pytest.warns(UserWarning, match="SECRET_KEY is not set"):
        second = _settings(monkeypatch)
    assert len(first.secret_key) == 64 and first.secret_key != second.secret_key


def test_set_secret_key_is_kept(monkeypatch):
    assert _settings(monkeypatch, SECRET_KEY="kept").secret_key == "kept"


def test_development_allows_all_origins_when_unset(monkeypatch):
    settings = _settings(monkeypatch, SECRET_KEY="k", ENVIRONMENT="development")
    assert settings.cors_allowed_origins == "*"


def test_production_warns_and_allows_none_when_unset(monkeypatch):
    with pytest.warns(UserWarning, match="CORS_ALLOWED_ORIGINS"):
        settings = _settings(monkeypatch, SECRET_KEY="k", ENVIRONMENT="production")
    assert settings.cors_allowed_origins == ""


def test_lock_directory_is_pyfinbots_own_unless_set(monkeypatch, tmp_path):
    default = _settings(monkeypatch, SECRET_KEY="k").lock_directory()
    assert Path(default) == Path(tempfile.gettempdir()) / "pyfinbot-locks"
    assert _settings(monkeypatch, SECRET_KEY="k", LOCK_DIR=str(tmp_path)).lock_directory() == str(tmp_path)


def test_sync_locks_live_in_the_lock_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(market_sync.settings, "lock_dir", str(tmp_path))
    market_sync._sync_locks.cache_clear()  # built once per process, from the setting at the time
    try:
        with market_sync.market_sync_guard("ASX") as acquired:
            assert acquired
            assert any(tmp_path.iterdir())
    finally:
        market_sync._sync_locks.cache_clear()
