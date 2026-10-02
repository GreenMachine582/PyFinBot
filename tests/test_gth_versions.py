"""The greentechhub packages are at the versions the code now relies on:
core's settings (including secret settings) and SQLAlchemy stores,
fastapi's register_settings (with cipher= and get_secret), ui's
settings-aware templates and write-only secret fields."""

from importlib.metadata import version

import pytest


def _parts(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.split(".")[:3])


@pytest.mark.parametrize(
    ("dist", "minimum"),
    [("greentechhub-core", "0.8.0"), ("greentechhub-fastapi", "0.10.0"), ("greentechhub-ui", "0.13.0")],
)
def test_greentechhub_versions(dist, minimum):
    assert _parts(version(dist)) >= _parts(minimum)


def test_core_settings_and_sqlalchemy_extra_are_available():
    from greentechhub_core.settings import Settings, SettingsRegistry
    from greentechhub_core.settings.builtins import USER_PREFERENCES
    from greentechhub_core.sqlalchemy import SQLAlchemySettingsStore, settings_table

    assert Settings and SettingsRegistry and USER_PREFERENCES
    assert SQLAlchemySettingsStore and settings_table


def test_fastapi_settings_and_permissions_are_available():
    from greentechhub_fastapi import register_permissions, register_settings
    from greentechhub_fastapi.settings import SettingsViews, settings_context

    assert register_permissions and register_settings and SettingsViews and settings_context
