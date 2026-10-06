"""The adapter settings (AUTH_ADAPTER, CORS_ALLOWED_ORIGINS, TRUSTED_PROXIES,
ROLE_BOOTSTRAP, ROLE_GROUPS) come from greentechhub-core's GTHBaseSettings
(item 8), not from fields PyFinBot declares itself."""
import pytest
from greentechhub_core.config import GTHBaseSettings

from pyfinbot.core.settings import Settings

ADAPTER_FIELDS = ["auth_adapter", "cors_allowed_origins", "trusted_proxies", "role_bootstrap",
                  "role_groups"]


def test_settings_declares_no_copies_of_its_own():
    own = set(Settings.model_fields) - set(GTHBaseSettings.model_fields)
    assert not own & {name.upper() for name in ADAPTER_FIELDS}
    assert set(ADAPTER_FIELDS) <= set(Settings.model_fields)


@pytest.mark.parametrize("field", ADAPTER_FIELDS)
def test_env_vars_reach_cores_fields(monkeypatch, field):
    monkeypatch.setenv(field.upper(), "from-env")
    assert getattr(Settings(_env_file=None), field) == "from-env"


def test_defaults_are_cores_safe_ones(monkeypatch):
    for field in ADAPTER_FIELDS:
        monkeypatch.delenv(field.upper(), raising=False)
    settings = Settings(_env_file=None)
    assert settings.auth_adapter == "local"
    assert settings.trusted_proxies == "" and settings.role_bootstrap == ""


def test_the_development_cors_default_lands_on_cores_field():
    # pyfinbot.py sets "*" in development when CORS_ALLOWED_ORIGINS is unset;
    # register_core read it from there (see test_settings' CORS middleware test).
    from pyfinbot.pyfinbot import settings

    assert settings.cors_allowed_origins == "*"
    assert not hasattr(settings, "CORS_ALLOWED_ORIGINS")
