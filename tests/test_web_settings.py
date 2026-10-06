"""Per-user preferences, /settings and the user menu (greentechhub v0.12
adoption, item 3): greentechhub-core settings in gth_settings, served by
greentechhub-fastapi's register_settings / SettingsViews."""
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

from pyfinbot.core.user_settings import DEFAULT_ROWS_PER_PAGE, USER_SETTINGS
from pyfinbot.dev.seed import seed_demo

from .conftest import create_stock, post_login, web_login
from .test_web_reports import HX, _txn

HTML = {"Accept": "text/html"}
ROOT = Path(__file__).resolve().parents[1]


async def _save_preferences(client, **values):
    data = {key.replace("__", "."): str(value) for key, value in values.items()}
    resp = await client.post("/settings/preferences", data=data, headers=HX)
    assert resp.status_code == 200, resp.text
    return resp


def _field_value(html: str, key: str) -> str:
    """The value a /settings number field renders with (gth_form_field)."""
    match = re.search(rf'id="gth-field-{re.escape(key)}"[^>]*?value="([^"]*)"', html, re.S)
    assert match, key
    return match.group(1)


# the registry


def test_registry_is_the_shared_preferences_with_pyfinbots_defaults():
    keys = {s.key for s in USER_SETTINGS}
    assert {"ui.theme", "locale.timezone", "locale.date_format", "ui.page_size",
            "locale.number_format", "locale.time_format"} <= keys
    assert USER_SETTINGS.get("ui.page_size").default == DEFAULT_ROWS_PER_PAGE
    assert USER_SETTINGS.get("locale.date_format").default == "long"
    assert "ui.sidebar_default" not in USER_SETTINGS  # navbar layout: it would do nothing
    # Everything is per user except the admins' Site group (Settings › App).
    assert {s.key for s in USER_SETTINGS if s.scope == "app"} == {"site.banner", "site.banner_tone"}


# access


async def test_settings_needs_login(client):
    resp = await client.get("/settings", headers=HTML, follow_redirects=False)
    assert resp.status_code == 303 and resp.headers["location"].startswith("/login")
    resp = await client.post("/settings/preferences", data={"ui.page_size": "10"}, headers=HX)
    assert resp.status_code == 401


async def test_settings_page_shows_preferences_only(client):
    await web_login(client, "settings-page")
    resp = await client.get("/settings", headers=HTML)
    assert resp.status_code == 200
    assert 'id="gth-settings-preferences"' in resp.text
    assert 'id="gth-settings-app"' not in resp.text
    for key in ("ui.theme", "locale.timezone", "locale.date_format", "ui.page_size"):
        assert f'gth-field-{key}' in resp.text, key
    assert _field_value(resp.text, "ui.page_size") == "50"


# per-user values


async def test_preferences_persist_per_user(client):
    await web_login(client, "settings-alice")
    saved = await _save_preferences(client, ui__page_size=10, locale__date_format="dmy")
    assert "HX-Trigger" in saved.headers
    assert _field_value((await client.get("/settings", headers=HTML)).text, "ui.page_size") == "10"

    await web_login(client, "settings-bob")
    assert _field_value((await client.get("/settings", headers=HTML)).text, "ui.page_size") == "50"


async def test_dates_follow_the_users_format(client):
    await web_login(client, "settings-dates")
    stock = await create_stock(client, symbol="STD")
    await _txn(client, stock["id"], "Buy", "10", "40", "2024-07-10")
    assert "10 Jul 2024" in (await client.get("/transactions", headers=HX)).text  # PyFinBot's default
    await _save_preferences(client, locale__date_format="dmy")
    page = (await client.get("/transactions", headers=HX)).text
    assert "10/07/2024" in page and "10 Jul 2024" not in page


async def test_rows_per_page_follow_the_user(client, session):
    await seed_demo(session, environment="development")  # demo-user: 52 transactions
    login = await post_login(client, "demo-user", "demo-user-pass",
                              follow_redirects=False)
    client.cookies.set("gth_session", login.cookies["gth_session"])

    def rows(html):
        return len(re.findall(r'hx-get="/(?:transactions|stocks)/\d+/edit"', html))  # one per row

    assert rows((await client.get("/transactions", headers=HX)).text) == 50
    await _save_preferences(client, ui__page_size=10)
    page = (await client.get("/transactions", headers=HX)).text
    assert rows(page) == 10 and "Load more" in page
    assert rows((await client.get("/stocks", headers=HX)).text) <= 10


# user menu and theme


async def test_user_menu_has_settings_and_log_out(client):
    await web_login(client, "settings-menu")
    page = (await client.get("/", headers=HTML)).text
    assert 'href="/settings"' in page
    assert page.count('action="/logout"') == 1  # the user menu's; the dashboard's own form is gone
    out = await client.post("/logout", follow_redirects=False)
    assert out.status_code == 303 and out.headers["location"] == "/login"
    client.cookies.clear()
    assert (await client.get("/", headers=HTML, follow_redirects=False)).status_code == 303


async def test_theme_toggle_saves_to_the_users_settings(client):
    await web_login(client, "settings-theme")
    resp = await client.post("/settings/theme", data={"theme": "light"}, headers=HX)
    assert resp.status_code == 204
    page = (await client.get("/", headers=HTML)).text
    assert 'var server = "light";' in page  # app.html's pre-paint theme script
    assert 'data-gth-theme-save-url="/settings/theme"' in page


# migration


def test_migration_creates_and_drops_gth_settings(tmp_path):
    db = tmp_path / "migrate.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db}",
           "ASYNC_DATABASE_URL": f"sqlite+aiosqlite:///{db}"}

    def alembic(*args):
        # A subprocess: alembic's env.py imports the models as src.pyfinbot,
        # which would redefine this process's tables.
        subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, check=True,
                       capture_output=True)

    def tables():
        with sqlite3.connect(db) as conn:
            return {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}

    alembic("upgrade", "head")
    assert "gth_settings" in tables()
    with sqlite3.connect(db) as conn:
        cols = [r[1] for r in conn.execute("pragma table_info(gth_settings)")]
    assert cols == ["scope", "subject", "key", "value", "updated_at"]
    alembic("downgrade", "a7ab2f6a51dc")  # back to before gth_settings
    assert "gth_settings" not in tables() and "dividend" in tables()
