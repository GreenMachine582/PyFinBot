"""greentechhub-ui v0.16 macros in place of PyFinBot's hand-built markup:
gth_result_panel for the import / sync results, gth_filter_bar (with
gth_download_button) and gth_stat_grid for the report panes,
gth_form_actions for the stock / transaction forms, gth_amount for signed
amounts, and ui's own |fy filter."""
from types import SimpleNamespace

import greentechhub_ui.formatting

from pyfinbot.web.templating import templates

from .conftest import create_stock, web_login
from .test_web_reports import _seed, _txn


def _render(name: str, **context) -> str:
    return templates.get_template(name).render(**context)


class TestResultPanels:
    def test_import_result_is_a_result_panel(self):
        summary = SimpleNamespace(total_rows=3, created=2, skipped=1,
                                  row_errors=[SimpleNamespace(row=4, message="Unknown stock")])
        html = _render("_import_result.html", summary=summary, filename="trades.csv")
        assert "gth-result-panel" in html and "Results — trades.csv" in html
        assert "2 imported" in html and "1 skipped" in html and "Unknown stock" in html
        assert 'href="/transactions"' in html

    def test_import_error_is_a_danger_alert(self):
        html = _render("_import_result.html", error="Empty file", filename="trades.csv")
        assert "gth-toast-danger" in html and "Couldn&#39;t import trades.csv" in html
        assert "gth-result-panel" not in html

    def test_sync_result_is_a_result_panel(self):
        html = _render("_sync_result.html", heading="Email sync", badges=[("1 imported", "good")],
                       problems=["Couldn't read one email"], link=("/transactions", "View transactions"))
        assert "gth-result-panel" in html and "gth-result-problems" in html
        assert "1 imported" in html and 'href="/transactions"' in html

    def test_sync_error_keeps_its_settings_action(self):
        html = _render("_sync_result.html", heading="Email sync", error="Not set up",
                       settings_url="/settings#email")
        assert "gth-toast-danger" in html and 'href="/settings#email"' in html


class TestReportPanes:
    async def test_panes_use_the_filter_bar_and_stat_grid(self, gth_client, gth_session):
        await web_login(gth_client, "macro-reports")
        await _seed(gth_client, gth_session)
        for pane, csv in [("holdings", "/reports/holdings.csv?as_of="), ("gains", "/reports/gains.csv?fy=2024"),
                          ("dividends", "/reports/dividends.csv")]:
            html = (await gth_client.get(f"/reports/{pane}")).text
            assert "gth-filter-bar" in html and 'hx-get="/reports/' + pane + '"' in html, pane
            assert "gth-download" in html and f'href="{csv}' in html, pane
            assert "gth-stat-grid" in html, pane

    async def test_a_loss_is_a_red_amount(self, gth_client):
        await web_login(gth_client, "macro-loss")
        stock = await create_stock(gth_client, "LOSS", "ASX", "Loss Co")
        await _txn(gth_client, stock["id"], "Buy", "10", "50", "2024-07-10")
        await _txn(gth_client, stock["id"], "Sell", "10", "40", "2024-08-10")
        html = (await gth_client.get("/reports/gains?fy=2024")).text
        assert 'gth-amount text-danger">-$100.00' in html


class TestForms:
    async def test_stock_and_transaction_forms_use_form_actions(self, gth_client):
        await web_login(gth_client, "macro-forms")
        for url in ("/stocks/new", "/transactions/new"):
            html = (await gth_client.get(url)).text
            assert "gth-form-actions" in html and 'data-bs-dismiss="modal"' in html, url


def test_fy_is_greentechhub_uis_filter():
    assert templates.env.filters["fy"] is greentechhub_ui.formatting.fiscal_year_label
