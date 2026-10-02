"""Roles, the admin pages and the locked-down users API (greentechhub v0.12
adoption, item 5): greentechhub-core's RoleResolver via greentechhub-
fastapi's register_permissions, with PyFinBot's admin role."""
import getpass
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from greentechhub_core.identity import Identity
from greentechhub_fastapi import register_permissions
from sqlalchemy import select

from pyfinbot.admin import create_user as create_user_module
from pyfinbot.admin.create_user import UserExists, create_user
from pyfinbot.core.permissions import ADMIN, ROLES, SETTINGS_MANAGE, USERS_MANAGE
from pyfinbot.core.security import verify_password
from pyfinbot.dev.seed import DEMO_ADMIN, seed_demo
from pyfinbot.models.settings_models import ROLE_GRANTS_TABLE
from pyfinbot.models.user_models import User

from .conftest import make_admin, register_and_login, web_login

HTML = {"Accept": "text/html"}
HX = {"HX-Request": "true"}


def test_the_admin_role():
    assert ROLES == (ADMIN,) and ADMIN.permissions == {USERS_MANAGE, SETTINGS_MANAGE}


async def test_role_bootstrap_makes_an_admin_without_any_grant():
    app = FastAPI()
    config = SimpleNamespace(ROLE_BOOTSTRAP="boss=admin", ROLE_GROUPS="")
    resolver = register_permissions(app, config, roles=ROLES)
    boss = Identity(subject="boss", username="boss", email=None, groups=[], claims={})
    other = Identity(subject="other", username="other", email=None, groups=[], claims={})
    assert USERS_MANAGE in await resolver.granted(boss)
    assert not await resolver.granted(other)


# the admin pages


async def test_admin_reaches_settings_app_and_roles(client):
    await web_login(client, "perm-admin")
    await make_admin(client, "perm-admin")
    home = (await client.get("/", headers=HTML)).text
    assert 'href="/admin/roles"' in home  # the admin-only nav item

    settings_page = (await client.get("/settings", headers=HTML)).text
    assert 'id="gth-settings-app"' in settings_page and "Site banner" in settings_page

    roles = await client.get("/admin/roles", headers=HTML)
    assert roles.status_code == 200 and "perm-admin" in roles.text

    await register_and_login(client, "perm-new")  # an existing user to promote
    resp = await client.post("/admin/roles", headers=HX, data={"subject": "perm-new", "roles": "admin"})
    assert resp.status_code == 200 and "perm-new" in resp.text


async def test_normal_user_has_no_admin_pages(client):
    await web_login(client, "perm-plain")
    home = (await client.get("/", headers=HTML)).text
    assert 'href="/admin/roles"' not in home
    assert (await client.get("/admin/roles", headers=HTML)).status_code == 403
    settings_page = (await client.get("/settings", headers=HTML)).text
    assert 'id="gth-settings-preferences"' in settings_page
    assert 'id="gth-settings-app"' not in settings_page
    resp = await client.post("/settings/app", headers=HX, data={"site.banner": "Hacked"})
    assert resp.status_code == 403


async def test_site_banner_set_by_an_admin_shows_for_everyone(client):
    await web_login(client, "banner-admin")
    await make_admin(client, "banner-admin")
    resp = await client.post("/settings/app", headers=HX, data={
        "site.banner": "Maintenance tonight 22:00", "site.banner_tone": "bad"})
    assert resp.status_code == 200, resp.text

    await web_login(client, "banner-reader")
    page = (await client.get("/", headers=HTML)).text
    assert 'data-gth-banner="site"' in page and "Maintenance tonight 22:00" in page
    assert "alert-danger" in page

    await web_login(client, "banner-admin-2")
    await make_admin(client, "banner-admin-2")
    await client.post("/settings/app", headers=HX, data={"site.banner": "", "site.banner_tone": "warn"})
    assert 'data-gth-banner="site"' not in (await client.get("/", headers=HTML)).text


# the users API


async def test_users_api_needs_users_manage(client):
    assert (await client.get("/api/users/")).status_code == 401
    assert (await client.post("/api/users/", json={"id": "x", "password": "y"})).status_code == 401
    plain = await register_and_login(client, "api-plain")
    assert (await client.get("/api/users/", headers=plain)).status_code == 403
    assert (await client.post("/api/users/", json={"id": "x", "password": "y"},
                              headers=plain)).status_code == 403
    admin = await register_and_login(client, "api-admin")
    await make_admin(client, "api-admin")
    assert (await client.get("/api/users/", headers=admin)).status_code == 200
    created = await client.post("/api/users/", json={"id": "api-made", "password": "pw"}, headers=admin)
    assert created.status_code == 201
    assert (await client.get("/api/users/api-made", headers=admin)).status_code == 403  # still self-only


# the first user


async def test_create_user_hashes_and_refuses_duplicates(session):
    user = await create_user(session, " first-admin ", "s3cret!")
    assert user.id == "first-admin" and user.active and verify_password("s3cret!", user.password_hash)
    with pytest.raises(UserExists):
        await create_user(session, "first-admin", "other")
    with pytest.raises(ValueError):
        await create_user(session, "  ", "pw")


def test_create_user_cli_refuses_mismatched_passwords(monkeypatch, capsys):
    answers = iter(["one", "two"])
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": next(answers))
    called = []
    monkeypatch.setattr(create_user_module, "_run", lambda *a: called.append(a))
    assert create_user_module.main(["someone"]) == 1
    assert "don't match" in capsys.readouterr().err and not called


def test_create_user_cli_prints_the_bootstrap_hint(monkeypatch, capsys):
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "pw")

    async def fake_run(user_id, password):
        return None

    monkeypatch.setattr(create_user_module, "_run", fake_run)
    assert create_user_module.main(["alice"]) == 0
    assert "ROLE_BOOTSTRAP=alice=admin" in capsys.readouterr().out


async def test_seed_grants_demo_admin_and_reset_removes_it(session):
    async def grants():
        rows = await session.exec(select(ROLE_GRANTS_TABLE.c.subject, ROLE_GRANTS_TABLE.c.role))
        return set(rows.all())

    summary = await seed_demo(session, environment="development")
    assert summary.grants_created == 1 and (DEMO_ADMIN, "admin") in await grants()
    again = await seed_demo(session, environment="development")
    assert again.grants_created == 0
    reset = await seed_demo(session, reset=True, environment="development")
    assert reset.reset["grants"] == 1 and reset.grants_created == 1
    assert await session.get(User, DEMO_ADMIN) is not None
