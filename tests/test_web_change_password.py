"""/settings › Password: greentechhub-fastapi's SettingsViews section with
PyFinBot's change_password hook over User.password_hash."""
import json
from html import unescape

from greentechhub_core.security import verify_password

from pyfinbot.models.user_models import User

from .conftest import web_login
from .test_web_reports import HX

GOOD = {"current_password": "hunter2!", "new_password": "brand-new-pass",
        "new_password_confirm": "brand-new-pass"}


async def _hash(session, user_id: str) -> str:
    session.expire_all()
    return (await session.get(User, user_id)).password_hash


async def test_the_settings_page_has_a_password_section(client):
    await web_login(client, "pw-page")
    resp = await client.get("/settings", headers={"Accept": "text/html"})
    assert resp.status_code == 200
    assert 'id="gth-settings-password"' in resp.text
    for name in ("current_password", "new_password", "new_password_confirm"):
        assert f'name="{name}"' in resp.text


async def test_a_wrong_current_password_changes_nothing(client, session):
    await web_login(client, "pw-wrong")
    before = await _hash(session, "pw-wrong")
    resp = await client.post("/settings/password", headers=HX,
                             data={**GOOD, "current_password": "not-it-at-all"})
    assert resp.status_code == 422
    assert "That isn't your current password." in unescape(resp.text)
    assert await _hash(session, "pw-wrong") == before


async def test_a_short_or_mismatched_new_password_is_refused(client, session):
    await web_login(client, "pw-checks")
    before = await _hash(session, "pw-checks")
    short = await client.post("/settings/password", headers=HX,
                              data={**GOOD, "new_password": "short", "new_password_confirm": "short"})
    mismatch = await client.post("/settings/password", headers=HX,
                                 data={**GOOD, "new_password_confirm": "something-else"})
    assert short.status_code == mismatch.status_code == 422
    assert await _hash(session, "pw-checks") == before


async def test_changing_it_signs_in_with_the_new_password_only(client, session):
    await web_login(client, "pw-change")
    resp = await client.post("/settings/password", headers=HX, data=GOOD)
    assert resp.status_code == 200
    assert json.loads(resp.headers["HX-Trigger"])["showToast"]["message"] == "Password changed"
    assert "hunter2!" not in resp.text and "brand-new-pass" not in resp.text
    assert verify_password("brand-new-pass", await _hash(session, "pw-change"))

    old = await client.post("/login", data={"user_id": "pw-change", "password": "hunter2!"},
                            follow_redirects=False)
    assert old.status_code == 401
    new = await client.post("/login", data={"user_id": "pw-change", "password": "brand-new-pass"},
                            follow_redirects=False)
    assert new.status_code == 303


async def test_anonymous_visitors_change_nothing(client, session):
    await web_login(client, "pw-anon")
    before = await _hash(session, "pw-anon")
    client.cookies.clear()
    resp = await client.post("/settings/password", headers=HX, data=GOOD, follow_redirects=False)
    assert resp.status_code == 401 and resp.headers["HX-Redirect"] == "/login"
    assert await _hash(session, "pw-anon") == before
