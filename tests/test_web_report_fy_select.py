"""The report panes' Financial year selects as greentechhub-ui's gth_select
(v0.15's id= prefix): both are name="fy" in tab panes that stay in the DOM,
so each keeps its own id (gains-fy, dividends-fy) and label."""

from .conftest import web_login
from .test_web_reports import _seed


async def test_gains_fy_is_a_gth_select_with_its_own_id(gth_client, gth_session):
    await web_login(gth_client, "web-fy-select")
    await _seed(gth_client, gth_session)
    resp = await gth_client.get("/reports/gains")
    html = resp.text
    assert '<div class="mb-0 gth-form-field gth-select">' in html
    assert '<label class="form-label" for="gains-fy">Financial year</label>' in html
    assert '<select id="gains-fy" name="fy" class="form-select">' in html
    assert '<option value="2024" selected>2024–25</option>' in html
    assert 'value=""' not in html.split('id="gains-fy"')[1].split("</select>")[0]  # no "All time"


async def test_dividends_fy_offers_all_time(gth_client, gth_session):
    await web_login(gth_client, "web-fy-select")
    await _seed(gth_client, gth_session)
    all_time = (await gth_client.get("/reports/dividends")).text
    assert '<select id="dividends-fy" name="fy" class="form-select">' in all_time
    assert '<option value="" selected>All time</option>' in all_time
    one_year = (await gth_client.get("/reports/dividends", params={"fy": "2024"})).text
    assert '<option value="2024" selected>2024–25</option>' in one_year
    assert '<option value="">All time</option>' in one_year


async def test_both_panes_on_one_page_keep_unique_ids(gth_client, gth_session):
    await web_login(gth_client, "web-fy-select")
    await _seed(gth_client, gth_session)
    page = (await gth_client.get("/reports")).text
    for pane in ("/reports/gains", "/reports/dividends"):
        page += (await gth_client.get(pane)).text  # what the tabs load into the same DOM
    assert 'id="gth-field-fy"' not in page
    assert page.count('id="gains-fy"') == 1 and page.count('id="dividends-fy"') == 1
