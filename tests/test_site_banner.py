"""The site banner comes from greentechhub: core's site_banner_settings()
replaces PyFinBot's hand-written site.banner / site.banner_tone settings
(same keys, so saved values carry over), and fastapi's settings_context
renders it, replacing web/templating.site_banners_context."""
from greentechhub_core.settings.builtins import site_banner_settings
from greentechhub_fastapi.settings import settings_context
from greentechhub_fastapi.templating import ui_context

from pyfinbot.core.permissions import SETTINGS_MANAGE
from pyfinbot.core.user_settings import USER_SETTINGS
from pyfinbot.web import templating

from .conftest import make_admin, web_login

HTML = {"Accept": "text/html"}
HX = {"HX-Request": "true"}


def test_the_banner_settings_are_cores():
    ours = [s for s in USER_SETTINGS if s.key.startswith("site.")]
    assert ours == list(site_banner_settings(edit_permission=SETTINGS_MANAGE))


def test_no_banner_context_processor_of_our_own():
    assert not hasattr(templating, "site_banners_context")
    assert templating.templates.context_processors == [ui_context, settings_context]


async def test_a_banner_in_a_core_only_tone_shows_once(client):
    await web_login(client, "banner-good")
    await make_admin(client, "banner-good")
    resp = await client.post("/settings/app", headers=HX, data={
        "site.banner": "Upgrade finished", "site.banner_tone": "good"})
    assert resp.status_code == 200, resp.text
    page = (await client.get("/", headers=HTML)).text
    assert page.count('data-gth-banner="site"') == 1
    assert "alert-success" in page and "Upgrade finished" in page


async def test_an_empty_banner_shows_nothing(client):
    await web_login(client, "banner-none")
    page = (await client.get("/", headers=HTML)).text
    assert 'data-gth-banner="site"' not in page
