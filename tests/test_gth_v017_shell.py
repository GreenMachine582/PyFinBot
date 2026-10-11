"""greentechhub-ui v0.17's shell: install() switches on gth_loading_bar, so a
signed-in page carries the bar and its script without PyFinBot opting in."""
from .conftest import web_login


async def test_pages_carry_the_loading_bar(gth_client):
    await web_login(gth_client, "gth-loading-bar")
    page = (await gth_client.get("/")).text
    assert 'class="gth-loading-bar" data-gth-loading-bar' in page
    assert "/js/loading-bar.js" in page
