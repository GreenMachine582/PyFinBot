"""Roles, the admin pages and the locked-down users API (greentechhub v0.12
adoption, item 5): greentechhub-core's RoleResolver via greentechhub-
fastapi's register_permissions, with PyFinBot's admin role."""
import getpass
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from greentechhub_core.identity import Identity
from greentechhub_core.security import verify_password
from greentechhub_fastapi import register_permissions
from sqlalchemy import select

from pyfinbot.admin import create_user as create_user_module
from pyfinbot.admin.create_user import UserExists, create_user
from pyfinbot.core.permissions import ADMIN, AUDIT_VIEW, ROLES, SETTINGS_MANAGE, USERS_MANAGE
from pyfinbot.dev.seed import DEMO_ADMIN, seed_demo
from pyfinbot.models.settings_models import ROLE_GRANTS_TABLE
from .conftest import account_row, make_admin, register_and_login, user_id, web_login

HTML = {"Accept": "text/html"}
HX = {"HX-Request": "true"}


def test_the_admin_role():
    assert ROLES == (ADMIN,) and ADMIN.permissions == {USERS_MANAGE, SETTINGS_MANAGE, AUDIT_VIEW}


async def test_role_bootstrap_makes_an_admin_without_any_grant():
    app = FastAPI()
    config = SimpleNamespace(ROLE_BOOTSTRAP="boss=admin", ROLE_GROUPS="")
    resolver = register_permissions(app, config, roles=ROLES)
    boss = Identity(subject="boss", username="boss", email=None, groups=[], claims={})
    other = Identity(subject="other", username="other", email=None, groups=[], claims={})
    assert USERS_MANAGE in await resolver.granted(boss)
    assert not await resolver.granted(other)


# the admin pages


async def test_admin_reaches_settings_app_and_roles(gth_client):
    await web_login(gth_client, "perm-admin")
    await make_admin(gth_client, "perm-admin")
    home = (await gth_client.get("/", headers=HTML)).text
    assert 'href="/admin/roles"' in home  # the admin-only nav item

    settings_page = (await gth_client.get("/settings", headers=HTML)).text
    assert 'id="gth-settings-app"' in settings_page and "Site banner" in settings_page

    roles = await gth_client.get("/admin/roles", headers=HTML)
    assert roles.status_code == 200 and "perm-admin" in roles.text

    await register_and_login(gth_client, "perm-new")  # an existing user to promote
    new_id = await user_id("perm-new")
    resp = await gth_client.post("/admin/roles", headers=HX, data={"subject": new_id, "roles": "admin"})
    assert resp.status_code == 200 and new_id in resp.text


async def test_normal_user_has_no_admin_pages(gth_client):
    await web_login(gth_client, "perm-plain")
    home = (await gth_client.get("/", headers=HTML)).text
    assert 'href="/admin/roles"' not in home
    assert (await gth_client.get("/admin/roles", headers=HTML)).status_code == 403
    settings_page = (await gth_client.get("/settings", headers=HTML)).text
    assert 'id="gth-settings-preferences"' in settings_page
    assert 'id="gth-settings-app"' not in settings_page
    resp = await gth_client.post("/settings/app", headers=HX, data={"site.banner": "Hacked"})
    assert resp.status_code == 403


async def test_site_banner_set_by_an_admin_shows_for_everyone(gth_client):
    await web_login(gth_client, "banner-admin")
    await make_admin(gth_client, "banner-admin")
    resp = await gth_client.post("/settings/app", headers=HX, data={
        "site.banner": "Maintenance tonight 22:00", "site.banner_tone": "bad"})
    assert resp.status_code == 200, resp.text

    await web_login(gth_client, "banner-reader")
    page = (await gth_client.get("/", headers=HTML)).text
    assert 'data-gth-banner="site"' in page and "Maintenance tonight 22:00" in page
    assert "alert-danger" in page

    await web_login(gth_client, "banner-admin-2")
    await make_admin(gth_client, "banner-admin-2")
    await gth_client.post("/settings/app", headers=HX, data={"site.banner": "", "site.banner_tone": "warn"})
    assert 'data-gth-banner="site"' not in (await gth_client.get("/", headers=HTML)).text


# the users API


async def test_users_api_needs_users_manage(gth_client):
    assert (await gth_client.get("/api/users/")).status_code == 401
    assert (await gth_client.post("/api/users/", json={"username": "x", "password": "y"})).status_code == 401
    plain = await register_and_login(gth_client, "api-plain")
    assert (await gth_client.get("/api/users/", headers=plain)).status_code == 403
    assert (await gth_client.post("/api/users/", json={"username": "x", "password": "y"},
                              headers=plain)).status_code == 403
    admin = await register_and_login(gth_client, "api-admin")
    await make_admin(gth_client, "api-admin")
    assert (await gth_client.get("/api/users/", headers=admin)).status_code == 200
    created = await gth_client.post("/api/users/", json={"username": "api-made", "password": "pw"},
                                    headers=admin)
    assert created.status_code == 201
    made = created.json()["id"]
    assert (await gth_client.get(f"/api/users/{made}", headers=admin)).status_code == 403  # still self-only


# the first user


async def test_create_user_hashes_and_refuses_duplicates(gth_client):
    user = await create_user(" First-Admin ", "s3cret!", email="admin@example.com")
    assert user.username == "first-admin" and user.active and verify_password("s3cret!", user.password_hash)
    assert user.email == "admin@example.com" and not user.email_verified
    with pytest.raises(UserExists):
        await create_user("first-admin", "other")
    with pytest.raises(ValueError):
        await create_user("  ", "pw")
    with pytest.raises(ValueError):
        await create_user("second", "")


async def test_role_bootstrap_matches_the_username(gth_client):
    """ROLE_BOOTSTRAP=alice=admin still makes the first admin, though the
    account's subject is a generated id."""
    from greentechhub_fastapi.permissions import RESOLVER_STATE_KEY

    from pyfinbot.pyfinbot import app

    user = await create_user("boot-admin", "s3cret!")
    resolver = getattr(app.state, RESOLVER_STATE_KEY)
    original = resolver._bootstrap
    resolver._bootstrap = {**original, "boot-admin": frozenset({ADMIN.name})}
    try:
        identity = Identity(subject=user.id, username=user.username, email=None, groups=[], claims={})
        assert ADMIN.name in await resolver.roles_for(identity)
    finally:
        resolver._bootstrap = original


def test_create_user_cli_refuses_mismatched_passwords(monkeypatch, capsys):
    answers = iter(["one", "two"])
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": next(answers))
    called = []
    monkeypatch.setattr(create_user_module, "_run", lambda *a: called.append(a))
    assert create_user_module.main(["someone"]) == 1
    assert "don't match" in capsys.readouterr().err and not called


def test_create_user_cli_prints_the_bootstrap_hint(monkeypatch, capsys):
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "pw")

    async def fake_run(username, password, email):
        return SimpleNamespace(username=username, id="0" * 32)

    monkeypatch.setattr(create_user_module, "_run", fake_run)
    assert create_user_module.main(["alice"]) == 0
    assert "ROLE_BOOTSTRAP=alice=admin" in capsys.readouterr().out


async def test_seed_grants_demo_admin_and_reset_removes_it(gth_session):
    async def grants():
        rows = await gth_session.exec(select(ROLE_GRANTS_TABLE.c.subject, ROLE_GRANTS_TABLE.c.role))
        return set(rows.all())

    summary = await seed_demo(gth_session, environment="development")
    admin_id = (await account_row(gth_session, DEMO_ADMIN)).id
    assert summary.grants_created == 1 and (admin_id, "admin") in await grants()
    again = await seed_demo(gth_session, environment="development")
    assert again.grants_created == 0
    reset = await seed_demo(gth_session, reset=True, environment="development")
    assert reset.reset["grants"] == 1 and reset.grants_created == 1
    assert await account_row(gth_session, DEMO_ADMIN) is not None
