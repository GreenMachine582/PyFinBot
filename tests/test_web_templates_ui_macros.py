"""Templates use greentechhub-ui's existing macros instead of hand-built
markup (todo › Lean now): gth_switch, gth_segmented's errors, gth_page_header,
gth_form, gth_table and the fy_options filter."""
import re

from httpx import AsyncClient

from .conftest import create_stock, web_login

HTML = {"Accept": "text/html"}


async def test_the_stock_edit_form_uses_a_switch_that_posts_on(client: AsyncClient):
    await web_login(client, "macros-a")
    stock = await create_stock(client, "MAC1")
    form = (await client.get(f"/stocks/{stock['id']}/edit")).text
    assert re.search(r'<input class="form-check-input" type="checkbox" role="switch" id="gth-field-is_active" '
                     r'name="is_active" value="on"', form)
    assert "archives the stock" in form

    resp = await client.post(f"/stocks/{stock['id']}", data={"name": "Renamed"})  # switch off
    assert resp.status_code == 204, resp.text
    switch = re.search(r'<input[^>]*id="gth-field-is_active"[^>]*>', (await client.get(f"/stocks/{stock['id']}/edit")).text)
    assert switch and " checked" not in switch.group(0)  # archived


async def test_a_type_error_renders_inside_the_segmented_field(client: AsyncClient):
    await web_login(client, "macros-b")
    stock = await create_stock(client, "MAC2")
    resp = await client.post("/transactions", data={
        "stock_id": str(stock["id"]), "transaction_date": "2024-08-01", "type": "Hold",
        "units": "10", "price": "1", "fees": "0", "notes": ""})
    assert resp.status_code == 422
    # gth_segmented lays the error out and links it to the radio group.
    assert re.search(r'role="group"[^>]*aria-describedby="[^"]*gth-field-type-error"', resp.text)
    assert re.search(r'<div class="invalid-feedback d-block" id="gth-field-type-error">Input should be', resp.text)


async def test_pages_use_the_header_form_and_table_macros(client: AsyncClient):
    await web_login(client, "macros-c")
    dashboard = (await client.get("/", headers=HTML)).text
    assert "gth-page-header" in dashboard and '<h2 class="mb-3">Dashboard</h2>' not in dashboard

    dividends = (await client.get("/dividends", headers=HTML)).text
    assert re.search(r'<form[^>]*class="gth-form[^"]*"[^>]*action="/dividends/sync"', dividends) \
        or re.search(r'<form[^>]*action="/dividends/sync"[^>]*class="gth-form', dividends)

    imports = (await client.get("/import", headers=HTML)).text
    assert "gth-table table-sm" in imports and "<code>date</code>" in imports


async def test_the_report_panes_fy_options_are_unchanged(client: AsyncClient):
    await web_login(client, "macros-d")
    stock = await create_stock(client, "MAC3")
    await client.post("/transactions", data={
        "stock_id": str(stock["id"]), "transaction_date": "2024-08-01", "type": "Buy",
        "units": "10", "price": "1", "fees": "0", "notes": ""})
    for pane in ("gains", "dividends"):
        html = (await client.get(f"/reports/{pane}", headers={"HX-Request": "true"})).text
        assert '<option value="2024"' in html and "2024–25" in html, pane
