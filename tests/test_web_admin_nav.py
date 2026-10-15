"""The "Admin" nav group (greentechhub-fastapi v0.17's register_admin): Roles
and Audit log under one group, each shown only to users who hold its
permission, and the group only when one of them shows. Both pages stay gated."""

import re

from greentechhub_ui.navigation import filter_by_scope

from pyfinbot.web.templating import ADMIN_VIEWS, templates

from .conftest import make_admin, web_login

HTML = {"Accept": "text/html"}
USER = {"username": "someone"}


def _admin_group():
    [group] = [item for item in templates.env.globals["nav_items"] if item["label"] == "Admin"]
    return group


def test_the_admin_group_lists_the_admin_pages_with_their_permissions():
    group = _admin_group()
    assert "url" not in group
    assert [(c["label"], c["url"], c["required_permission"]) for c in group["children"]] == [
        ("Roles", "/admin/roles", "users.manage"), ("Audit log", "/admin/audit", "audit.view")]
    assert [view.url for view in ADMIN_VIEWS] == ["/admin/roles", "/admin/audit"]


def test_each_user_sees_only_the_admin_pages_they_can_open():
    nav = [_admin_group()]

    def labels(granted):
        return [c["label"] for item in filter_by_scope(nav, USER, granted) for c in item["children"]]

    assert labels({"users.manage", "audit.view"}) == ["Roles", "Audit log"]
    assert labels({"audit.view"}) == ["Audit log"]
    assert filter_by_scope(nav, USER, set()) == []  # no group at all
    assert filter_by_scope(nav, None, None) == []  # anonymous


async def test_admins_get_the_group_and_others_dont(gth_client):
    await web_login(gth_client, "nav-viewer")
    home = (await gth_client.get("/", headers=HTML)).text
    assert 'href="/admin/roles"' not in home and 'href="/admin/audit"' not in home
    assert (await gth_client.get("/admin/roles", headers=HTML)).status_code == 403
    assert (await gth_client.get("/admin/audit", headers=HTML)).status_code == 403

    await web_login(gth_client, "nav-admin")
    await make_admin(gth_client, "nav-admin")
    home = (await gth_client.get("/", headers=HTML)).text
    assert re.search(r"dropdown-toggle[^>]*>(?:\s|<i[^>]*></i>)*Admin\s*<", home)  # the group
    assert 'href="/admin/roles"' in home and 'href="/admin/audit"' in home
    assert (await gth_client.get("/admin/roles", headers=HTML)).status_code == 200
    assert (await gth_client.get("/admin/audit", headers=HTML)).status_code == 200


def test_the_audit_page_is_mounted_once():
    from pyfinbot.pyfinbot import app
    from starlette.routing import Match

    scope = {"type": "http", "path": "/admin/audit", "method": "GET", "root_path": "",
             "headers": [], "query_string": b""}
    assert sum(route.matches(scope)[0] == Match.FULL for route in app.router.routes) == 1
