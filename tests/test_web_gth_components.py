"""greentechhub-ui v0.14 macros in place of PyFinBot's hand-built markup:
gth_alert for the inline alerts, gth_busy_button(submit=True) for the
import / dividend form buttons, and gth_select / gth_form_field for the
filter bars and the holdings as-of date."""
import io
from unittest.mock import patch

from pyfinbot.core.email_sync import NOT_CONFIGURED, GmailNotConfiguredError

from .conftest import create_stock, web_login

HX = {"HX-Request": "true"}


class TestAlerts:
    async def test_email_setup_notice_is_an_inline_warning(self, client):
        await web_login(client, "gth-alerts")
        page = (await client.get("/emails")).text
        assert "gth-toast-inline gth-toast-warning" in page
        assert "Your email account isn't set up yet" in page
        assert '<a href="/settings#gth-settings-preferences">Settings › Email sync</a>' in page
        assert 'class="alert' not in page

    async def test_sync_error_is_an_inline_danger_alert_with_a_settings_action(self, client):
        await web_login(client, "gth-alerts")
        with patch("pyfinbot.core.commsec_import.fetch_commsec_emails",
                   side_effect=GmailNotConfiguredError(NOT_CONFIGURED)):
            resp = await client.post("/emails/sync", headers=HX)
        assert resp.status_code == 422
        assert "gth-toast-inline gth-toast-danger" in resp.text
        assert '<div class="gth-toast-title">' in resp.text
        assert 'class="gth-toast-action" href="/settings#gth-settings-preferences">Open Settings</a>' in resp.text
        assert 'class="alert' not in resp.text

    async def test_import_error_is_an_inline_danger_alert(self, client):
        await web_login(client, "gth-alerts")
        resp = await client.post("/import", headers=HX,
                                 files={"file": ("trades.csv", io.BytesIO(b""), "text/csv")})
        assert resp.status_code == 422
        assert "gth-toast-inline gth-toast-danger" in resp.text
        assert '<div class="gth-toast-title">Couldn&#39;t import trades.csv</div>' in resp.text
        assert "Uploaded file is empty" in resp.text
        assert 'class="alert' not in resp.text


class TestBusySubmitButtons:
    async def test_import_and_dividend_forms_use_submit_busy_buttons(self, client):
        await web_login(client, "gth-busy")
        for path, btn_class, label in (("/import", "btn-primary", "Import"),
                                       ("/dividends", "btn-outline-secondary", "Sync")):
            page = (await client.get(path)).text
            assert 'hx-disabled-elt="find button[type=submit]"' in page
            assert f'<button type="submit" class="btn {btn_class} gth-busy-button"' in page
            assert f"</i> {label}</span>" in page


class TestFilterSelects:
    async def test_transaction_filters_are_gth_selects(self, client):
        await web_login(client, "gth-selects")
        stock = await create_stock(client)
        resp = await client.post("/transactions", data={
            "stock_id": str(stock["id"]), "transaction_date": "2024-08-01", "type": "Buy",
            "units": "10", "price": "25.5", "fees": "9.95", "notes": ""})
        assert resp.status_code == 204, resp.text
        page = (await client.get("/transactions", params={"type": "Sell", "fy": "2024"})).text
        assert '<label class="form-label visually-hidden" for="gth-field-type">Type</label>' in page
        assert '<label class="form-label visually-hidden" for="gth-field-fy">Financial year</label>' in page
        assert '<option value="Sell" selected>Sell</option>' in page
        assert '<option value="2024" selected>2024–25</option>' in page
        assert '<option value="">All years</option>' in page

    async def test_stock_filters_are_gth_selects(self, client):
        await web_login(client, "gth-selects")
        await create_stock(client)
        page = (await client.get("/stocks")).text
        assert '<label class="form-label visually-hidden" for="gth-field-market">Market</label>' in page
        assert '<option value="" selected>All markets</option>' in page
        assert '<option value="active" selected>' in page  # status defaults to active
        page = (await client.get("/stocks", params={"market": "ASX", "status": "archived"})).text
        assert '<option value="ASX" selected>ASX</option>' in page
        assert '<option value="archived" selected>' in page


class TestHoldingsAsOf:
    async def test_as_of_is_a_gth_form_field(self, client):
        await web_login(client, "gth-holdings")
        pane = (await client.get("/reports/holdings", headers=HX, params={"as_of": "2025-01-31"})).text
        assert '<label class="form-label" for="gth-field-as_of">As of</label>' in pane
        assert 'type="date" id="gth-field-as_of" name="as_of"' in pane
        assert 'value="2025-01-31"' in pane
