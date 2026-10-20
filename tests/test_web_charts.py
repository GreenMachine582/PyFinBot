"""Charts (greentechhub-ui v0.17's server-rendered SVG): sparklines in the
dashboard's cost base and dividends tiles, net gain/loss by FY on the gains
pane and dividends by month on the dividends pane, from core/report_series.py
(built on the same report functions as the tables)."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from pyfinbot.core import report_series, reports

from .conftest import create_stock, user_id, web_login
from .test_reports import _seed_dividend
from .test_web_reports import _seed, _txn

HTML = {"Accept": "text/html"}


def _item(ex_date: str, amount: str):
    return SimpleNamespace(ex_date=date.fromisoformat(ex_date), amount_received=float(amount))


class TestSeries:
    def test_dividends_by_month_fills_and_sums(self):
        items = [_item("2024-07-05", "1.50"), _item("2024-07-20", "2.25"), _item("2024-09-01", "3"),
                 _item("2023-01-01", "99")]  # outside the window
        series = report_series.dividends_by_month(items, date(2024, 7, 1), date(2024, 10, 31))
        assert series == [("Jul 24", Decimal("3.75")), ("Aug 24", 0), ("Sep 24", Decimal("3")), ("Oct 24", 0)]

    def test_months_ago_crosses_a_year(self):
        assert report_series.months_ago(date(2025, 2, 14), 11) == date(2024, 3, 1)

    async def test_cost_base_by_month_ends_with_todays(self, gth_client, gth_session):
        await web_login(gth_client, "series-cost")
        await _seed(gth_client, gth_session)
        today = date(2025, 6, 30)
        series = await report_series.cost_base_by_month(gth_session, await user_id("series-cost"), today)
        holdings = await reports.holdings_report(gth_session, await user_id("series-cost"), today)
        assert len(series) == 12 and series[-1][0] == "Jun 25"
        assert series[-1][1] == sum(Decimal(str(h.units_held)) * Decimal(str(h.avg_cost_basis))
                                    for h in holdings.holdings)
        assert series[0] == ("Jul 24", Decimal("4000"))  # 31 Jul: the 10 Jul buy, 100 @ 40

    async def test_gains_by_fy_matches_the_report(self, gth_client, gth_session):
        await web_login(gth_client, "series-gains")
        await _seed(gth_client, gth_session)
        series = await report_series.gains_by_fy(gth_session, await user_id("series-gains"), [2024, 2023])
        gains_2024 = await reports.capital_gains_report(gth_session, await user_id("series-gains"), 2024)
        assert [label for label, _ in series] == ["2023–24", "2024–25"]
        assert series[1][1] == Decimal(str(gains_2024.total_gain_loss)) and series[0][1] == 0


class TestDashboard:
    async def test_tiles_carry_sparklines(self, gth_client, gth_session):
        await web_login(gth_client, "chart-dash")
        stock = await create_stock(gth_client, "SPK", "ASX", "Spark Co")
        today = date.today()
        await _txn(gth_client, stock["id"], "Buy", "10", "20", report_series.months_ago(today, 3).isoformat())
        await _seed_dividend(gth_session, stock["id"], report_series.months_ago(today, 1), "0.50")
        page = (await gth_client.get("/", headers=HTML)).text
        assert page.count('class="gth-sparkline') == 2 and 'role="img"' in page
        assert 'aria-label="Cost base, last 12 months' in page

    async def test_no_history_no_sparklines(self, gth_client):
        await web_login(gth_client, "chart-empty")
        page = await gth_client.get("/", headers=HTML)
        assert page.status_code == 200 and "gth-sparkline" not in page.text


class TestReportPanes:
    async def test_gains_bar_chart_over_two_fys(self, gth_client, gth_session):
        await web_login(gth_client, "chart-gains")
        bhp = await _seed(gth_client, gth_session)  # FY 2024: a sell
        await _txn(gth_client, bhp["id"], "Sell", "10", "30", "2025-08-01")  # FY 2025: a loss
        html = (await gth_client.get("/reports/gains")).text
        assert 'class="gth-chart gth-bar-chart' in html
        assert "Net gain/loss by financial year" in html and "<th scope=\"row\">2024–25</th>" in html

    async def test_one_fy_no_bar_chart(self, gth_client, gth_session):
        await web_login(gth_client, "chart-one-fy")
        await _seed(gth_client, gth_session)
        assert "gth-bar-chart" not in (await gth_client.get("/reports/gains")).text

    async def test_dividends_line_chart(self, gth_client, gth_session):
        await web_login(gth_client, "chart-divs")
        await _seed(gth_client, gth_session)
        html = (await gth_client.get("/reports/dividends?fy=2024")).text
        assert 'class="gth-chart gth-line-chart' in html and "Dividends received by month" in html
        assert '<th scope="row">Sep 24</th>' in html

    async def test_no_dividends_no_line_chart(self, gth_client):
        await web_login(gth_client, "chart-no-divs")
        assert "gth-line-chart" not in (await gth_client.get("/reports/dividends")).text
