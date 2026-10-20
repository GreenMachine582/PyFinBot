"""Personal API tokens (greentechhub-core v0.15's token store, greentechhub-fastapi
v0.17's register_api_tokens and ApiTokenViews, ui v0.19's API tokens section):
a user creates one at /settings, a script uses it as `Authorization: Bearer`,
and revoking it refuses the next call."""

import re

from .conftest import web_login

HX = {"HX-Request": "true"}
HTML = {"Accept": "text/html"}


async def _create(client, name="backup script", expiry="90"):
    resp = await client.post("/settings/api-tokens", headers=HX,
                             data={"name": name, "expires_in_days": expiry})
    assert resp.status_code == 200, resp.text
    plaintext = re.search(r'id="gth-settings-api_tokens-new-token" value="([^"]+)"', resp.text).group(1)
    token_id = re.search(r'hx-delete="/settings/api-tokens/([0-9a-f]{32})"', resp.text).group(1)
    return plaintext, token_id


async def test_a_script_authenticates_with_a_token_until_it_is_revoked(gth_client):
    await web_login(gth_client, "pat-user")
    page = await gth_client.get("/settings", headers=HTML)
    assert 'id="gth-settings-api_tokens"' in page.text

    plaintext, token_id = await _create(gth_client)
    bearer = {"Authorization": f"Bearer {plaintext}"}
    assert (await gth_client.get("/api/transactions/", headers=bearer)).status_code == 200

    revoked = await gth_client.delete(f"/settings/api-tokens/{token_id}", headers=HX)
    assert revoked.status_code == 200
    assert (await gth_client.get("/api/transactions/", headers=bearer)).status_code == 401


async def test_the_plaintext_is_shown_once(gth_client):
    await web_login(gth_client, "pat-once")
    plaintext, _ = await _create(gth_client)
    assert plaintext not in (await gth_client.get("/settings", headers=HTML)).text


async def test_a_token_cant_create_tokens(gth_client):
    await web_login(gth_client, "pat-self")
    plaintext, _ = await _create(gth_client)
    resp = await gth_client.post("/settings/api-tokens", headers={**HX, "Authorization": f"Bearer {plaintext}"},
                                 data={"name": "more", "expires_in_days": "90"})
    assert resp.status_code == 403
