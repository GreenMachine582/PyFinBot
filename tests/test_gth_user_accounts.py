"""User accounts on greentechhub-core's gth_users (core/users.py), wired by
register_users: the profile and its emailed confirmation, "Forgot password?",
notices by email to a confirmed address, and an inactive account signed out
on its next request."""
import io
import re

import pytest
from greentechhub_core.email import InMemoryEmailSender
from greentechhub_fastapi.auth.accounts import get_users_config
from greentechhub_fastapi.email import EMAIL_STATE_KEY

from pyfinbot.core.users import USER_STORE
from pyfinbot.pyfinbot import app

from .conftest import create_stock, post_login, send_csrf, user_id, web_login

HX = {"HX-Request": "true"}
HTML = {"Accept": "text/html"}
LINK = re.compile(r"https://pyfinbot\.test(/\S+)")
CSV = "date,stock,type,units,price,fees,notes\n2024-08-01,ASX:ACC,Buy,10,20,0,\n"


@pytest.fixture
def outbox(monkeypatch):
    """Emails go to an InMemoryEmailSender, with links on https://pyfinbot.test."""
    from dataclasses import replace

    sender = InMemoryEmailSender()
    config = replace(getattr(app.state, EMAIL_STATE_KEY), sender=sender,
                     base_url="https://pyfinbot.test")
    monkeypatch.setattr(app.state, EMAIL_STATE_KEY, config)
    return sender.outbox


def _link(message) -> str:
    return LINK.search(message.text).group(1)


def test_register_users_resolves_through_the_user_store():
    config = get_users_config(app)
    assert config.store is USER_STORE and config.idp_label == "Authentik"


async def test_the_profile_saves_and_confirms_a_changed_email(gth_client, outbox):
    await web_login(gth_client, "acct-profile")
    page = (await gth_client.get("/settings", headers=HTML)).text
    assert 'id="gth-settings-profile"' in page and 'type="email"' in page
    resp = await gth_client.post("/settings/profile", headers=HX,
                                 data={"display_name": "Profile Person", "email": "Me@Example.com"})
    assert resp.status_code == 200, resp.text
    assert "emailed a link to confirm" in resp.headers["HX-Trigger"]
    account = await USER_STORE.by_username("acct-profile")
    assert (account.display_name, account.email, account.email_verified) == (
        "Profile Person", "me@example.com", False)
    assert "Not confirmed yet." in resp.text

    [message] = outbox
    assert message.to == ("me@example.com",)
    confirmed = await gth_client.get(_link(message), headers=HTML)
    assert confirmed.status_code == 200
    assert (await USER_STORE.by_username("acct-profile")).email_verified
    assert "Profile Person" in (await gth_client.get("/", headers=HTML)).text  # the navbar's name


async def test_a_taken_email_is_a_profile_error(gth_client, outbox):
    await web_login(gth_client, "acct-first")
    await gth_client.post("/settings/profile", headers=HX, data={"display_name": "", "email": "same@example.com"})
    await web_login(gth_client, "acct-second")
    resp = await gth_client.post("/settings/profile", headers=HX,
                                 data={"display_name": "", "email": "SAME@example.com"})
    assert resp.status_code == 422 and "already used by another account" in resp.text


async def test_forgot_password_emails_a_working_reset_link(gth_client, outbox):
    await web_login(gth_client, "acct-forgot")
    me = await user_id("acct-forgot")
    await USER_STORE.update(me, {"email": "forgot@example.com"})
    login_page = (await gth_client.get("/login", headers=HTML)).text
    assert 'href="/forgot-password"' in login_page

    send_csrf(gth_client)
    token = gth_client.headers["X-CSRF-Token"]
    sent = await gth_client.post("/forgot-password", data={"identifier": "forgot@example.com",
                                                           "csrf_token": token})
    assert sent.status_code == 200
    [message] = outbox
    reset = await gth_client.post(_link(message), data={"password": "a-brand-new-pass",
                                                         "password_confirm": "a-brand-new-pass",
                                                         "csrf_token": token})
    assert reset.status_code == 200, reset.text
    assert (await post_login(gth_client, "acct-forgot", "a-brand-new-pass",
                             follow_redirects=False)).status_code == 303
    assert (await post_login(gth_client, "acct-forgot", "hunter2!",
                             follow_redirects=False)).status_code == 401


async def test_notices_can_be_emailed_to_a_confirmed_address(gth_client, outbox):
    await web_login(gth_client, "acct-notify")
    me = await user_id("acct-notify")
    await USER_STORE.update(me, {"email": "notify@example.com", "email_verified": True})
    saved = await gth_client.post("/settings/preferences", headers=HX, data={"notify.sync": "both"})
    assert saved.status_code == 200, saved.text
    await create_stock(gth_client, "ACC", "ASX", "Account Co")
    resp = await gth_client.post("/import", headers=HX,
                                 files={"file": ("t.csv", io.BytesIO(CSV.encode()), "text/csv")})
    assert resp.status_code == 200, resp.text
    assert [m for m in outbox if "notify@example.com" in str(m.to)]


async def test_an_unconfirmed_address_gets_no_notices(gth_client, outbox):
    await web_login(gth_client, "acct-unconfirmed")
    await USER_STORE.update(await user_id("acct-unconfirmed"), {"email": "nope@example.com"})
    await gth_client.post("/settings/preferences", headers=HX, data={"notify.sync": "email"})
    await create_stock(gth_client, "ACC", "ASX", "Account Co")
    await gth_client.post("/import", headers=HX,
                          files={"file": ("t.csv", io.BytesIO(CSV.encode()), "text/csv")})
    assert outbox == []


async def test_an_inactive_account_is_signed_out_on_its_next_request(gth_client):
    await web_login(gth_client, "acct-off")
    assert (await gth_client.get("/", headers=HTML, follow_redirects=False)).status_code == 200
    await USER_STORE.update(await user_id("acct-off"), {"active": False})
    page = await gth_client.get("/", headers=HTML, follow_redirects=False)
    assert page.status_code == 303 and page.headers["location"].startswith("/login")


def test_scim_is_off_without_a_token():
    assert not any(getattr(route, "path", "").startswith("/scim/") for route in app.routes)
