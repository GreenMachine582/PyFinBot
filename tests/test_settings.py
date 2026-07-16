"""Unit tests for core/settings.py's CORS/environment configuration."""
import importlib
import sys
import warnings

import pytest

from pyfinbot.core.settings import Settings


def _settings_module():
    """The actual core.settings module object, for importlib.reload().

    `import pyfinbot.core.settings as x` would bind `x` to the module's
    `settings` *instance* instead, because `pyfinbot/core/__init__.py` does
    `from .settings import settings as settings`, which shadows the
    auto-registered submodule attribute on the `core` package — a classic
    Python footgun. sys.modules is unaffected by that shadowing.
    """
    import pyfinbot.core.settings  # noqa: F401  ensures it's registered
    return sys.modules["pyfinbot.core.settings"]


class TestCorsOriginsList:
    def test_empty_string_is_empty_list(self):
        assert Settings(CORS_ORIGINS="").cors_origins_list == []

    def test_single_origin(self):
        assert Settings(CORS_ORIGINS="https://example.com").cors_origins_list == ["https://example.com"]

    def test_multiple_origins_split_on_comma(self):
        s = Settings(CORS_ORIGINS="https://a.com,https://b.com")
        assert s.cors_origins_list == ["https://a.com", "https://b.com"]

    def test_whitespace_and_empties_stripped(self):
        s = Settings(CORS_ORIGINS=" https://a.com , , https://b.com ,")
        assert s.cors_origins_list == ["https://a.com", "https://b.com"]


class TestProductionCorsWarning:
    def test_warns_when_production_and_no_cors_origins(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        settings_module = _settings_module()
        with pytest.warns(UserWarning, match="CORS_ORIGINS"):
            importlib.reload(settings_module)
        # restore module state for subsequent tests/imports in this process
        monkeypatch.undo()
        importlib.reload(settings_module)

    def test_no_warning_when_production_and_cors_origins_set(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("CORS_ORIGINS", "https://example.com")
        settings_module = _settings_module()
        # SECRET_KEY is unset in the test env too, so it also warns on every
        # reload — record everything and only assert on the CORS message,
        # rather than treating all UserWarnings as failures.
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            importlib.reload(settings_module)
        monkeypatch.undo()
        importlib.reload(settings_module)
        assert not any("CORS_ORIGINS" in str(w.message) for w in caught)

    def test_no_warning_when_development_and_no_cors_origins(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        settings_module = _settings_module()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            importlib.reload(settings_module)
        monkeypatch.undo()
        importlib.reload(settings_module)
        assert not any("CORS_ORIGINS" in str(w.message) for w in caught)


class TestCorsMiddlewareRegistration:
    def test_cors_middleware_registered_with_dev_default(self):
        from pyfinbot.pyfinbot import app
        from fastapi.middleware.cors import CORSMiddleware

        cors_entries = [m for m in app.user_middleware if m.cls is CORSMiddleware]
        assert len(cors_entries) == 1
        # Test process runs with no ENVIRONMENT/CORS_ORIGINS override — dev default applies
        assert cors_entries[0].kwargs["allow_origins"] == ["*"]
        assert cors_entries[0].kwargs["allow_credentials"] is True
