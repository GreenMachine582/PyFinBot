"""Integration tests for the /reports web page."""
import csv
import io

from httpx import AsyncClient

from .conftest import create_stock, web_login
from .test_reports import _seed_dividend

HX = {"HX-Request": "true"}


async def _txn(client: AsyncClient, stock_id: int, type_: str, units: str, price: str, day: str,
               fees: str = "0") -> None:
    resp = await client.post("/transactions", data={
        "stock_id": stock_id, "transaction_date": day, "type": type_,
        "units": units, "price": price, "fees": fees,
    })
    assert resp.status_code == 204, resp.text


async def _seed(client: AsyncClient, session) -> dict:
    """BHP: buy 100 @ 40 and 100 @ 50 (avg 45), sell 50 @ 60 less 10 fees in
    FY2024 → gain 740; a 1.50 dividend while 200 were held → 300."""
    bhp = await create_stock(client)
    await _txn(client, bhp["id"], "Buy", "100", "40", "2024-07-10")
    await _txn(client, bhp["id"], "Buy", "100", "50", "2024-08-10")
    await _seed_dividend(session, bhp["id"], "2024-09-01", "1.50")
    await _txn(client, bhp["id"], "Sell", "50", "60", "2025-01-15", fees="10")
    return bhp


def _csv(resp) -> list[list[str]]:
    return list(csv.reader(io.StringIO(resp.text)))


class TestAuthGuard:
    async def test_page_redirects_to_login(self, client):
        resp = await client.get("/reports", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/login"

    async def test_pane_gets_hx_redirect(self, client):
        resp = await client.get("/reports/holdings", headers=HX, follow_redirects=False)
        assert resp.status_code == 401
        assert resp.headers["HX-Redirect"] == "/login"

    async def test_csv_redirects_to_login(self, client):
        resp = await client.get("/reports/holdings.csv", follow_redirects=False)
        assert resp.status_code == 303


class TestPage:
    async def test_renders_lazy_tabs(self, client):
        await web_login(client, "web-reports")
        resp = await client.get("/reports")
        assert resp.status_code == 200
        for url in ("/reports/holdings", "/reports/gains", "/reports/dividends"):
            assert f'hx-get="{url}"' in resp.text
        assert 'href="/reports" aria-current="page"' in resp.text

    async def test_tab_param_picks_the_open_tab(self, client):
        await web_login(client, "web-reports")
        resp = await client.get("/reports", params={"tab": "gains"})
        assert 'class="nav-link active" id="reports-tab-gains"' in resp.text
        resp = await client.get("/reports", params={"tab": "bogus"})
        assert 'class="nav-link active" id="reports-tab-holdings"' in resp.text


class TestHoldings:
    async def test_holdings(self, client, session):
        await web_login(client, "web-reports")
        await _seed(client, session)
        resp = await client.get("/reports/holdings", headers=HX, params={"as_of": "2025-06-30"})
        assert resp.status_code == 200
        assert "<html" not in resp.text
        assert "BHP Group" in resp.text
        assert ">150<" in resp.text            # units held
        assert "45.00" in resp.text            # avg cost
        assert "6,750.00" in resp.text         # cost base 150 × 45
        assert "300.00" in resp.text           # dividend: 200 units × 1.50
        assert 'href="/reports/holdings.csv?as_of=2025-06-30"' in resp.text

    async def test_as_of_before_first_buy_is_empty(self, client, session):
        await web_login(client, "web-reports")
        await _seed(client, session)
        resp = await client.get("/reports/holdings", params={"as_of": "2024-01-01"})
        assert "You held no stocks on 2024-01-01." in resp.text

    async def test_bad_date_falls_back_to_today(self, client):
        await web_login(client, "web-reports")
        resp = await client.get("/reports/holdings", params={"as_of": "not-a-date"})
        assert resp.status_code == 200

    async def test_only_own_transactions(self, client, session):
        await web_login(client, "web-reports-a")
        await _seed(client, session)
        await web_login(client, "web-reports-b")
        resp = await client.get("/reports/holdings", params={"as_of": "2025-06-30"})
        assert "BHP Group" not in resp.text

    async def test_csv(self, client, session):
        await web_login(client, "web-reports")
        await _seed(client, session)
        resp = await client.get("/reports/holdings.csv", params={"as_of": "2025-06-30"})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert 'filename="pyfinbot-holdings-2025-06-30.csv"' in resp.headers["content-disposition"]
        rows = _csv(resp)
        assert rows[0][:3] == ["Market", "Symbol", "Name"]
        assert rows[1][:4] == ["ASX", "BHP", "BHP Group", "150.0"]
        assert float(rows[1][5]) == 6750 and float(rows[1][6]) == 300


class TestGains:
    async def test_defaults_to_latest_fy(self, client, session):
        await web_login(client, "web-reports")
        await _seed(client, session)
        resp = await client.get("/reports/gains")
        assert '<option value="2024" selected>2024–25</option>' in resp.text
        assert "740.00" in resp.text  # 50 × 60 − 10 − 50 × 45
        assert "text-success" in resp.text

    async def test_fy_without_sells(self, client, session):
        await web_login(client, "web-reports")
        await _seed(client, session)
        resp = await client.get("/reports/gains", params={"fy": "2023"})
        assert "No sells in FY 2023–24." in resp.text

    async def test_no_transactions_uses_current_fy(self, client):
        await web_login(client, "web-reports")
        resp = await client.get("/reports/gains")
        assert resp.status_code == 200
        assert "No sells in FY" in resp.text

    async def test_csv(self, client, session):
        await web_login(client, "web-reports")
        await _seed(client, session)
        resp = await client.get("/reports/gains.csv", params={"fy": "2024"})
        assert 'filename="pyfinbot-gains-fy2024.csv"' in resp.headers["content-disposition"]
        rows = _csv(resp)
        assert rows[0][-1] == "Gain/loss"
        assert float(rows[1][-1]) == 740


class TestDividends:
    async def test_all_time_and_fy(self, client, session):
        await web_login(client, "web-reports")
        await _seed(client, session)
        resp = await client.get("/reports/dividends")
        assert "Received, all time" in resp.text
        assert "2024-09-01" in resp.text and "300.00" in resp.text
        assert 'href="/reports/dividends.csv"' in resp.text

        resp = await client.get("/reports/dividends", params={"fy": "2024"})
        assert "300.00" in resp.text
        assert 'href="/reports/dividends.csv?fy=2024"' in resp.text

        resp = await client.get("/reports/dividends", params={"fy": "2023"})
        assert "No dividends received in FY 2023–24." in resp.text

    async def test_csv(self, client, session):
        await web_login(client, "web-reports")
        await _seed(client, session)
        resp = await client.get("/reports/dividends.csv")
        assert 'filename="pyfinbot-dividends-all.csv"' in resp.headers["content-disposition"]
        rows = _csv(resp)
        assert rows[0][0] == "Ex date"
        assert rows[1][0] == "2024-09-01" and float(rows[1][-1]) == 300

    async def test_unknown_csv_is_404(self, client):
        await web_login(client, "web-reports")
        resp = await client.get("/reports/bogus.csv")
        assert resp.status_code == 404
