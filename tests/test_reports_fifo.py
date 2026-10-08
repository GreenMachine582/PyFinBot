"""FIFO cost basis for the holdings and capital-gains reports (API and web),
next to the default average method, which must not change."""
import pytest

from .conftest import create_stock, register_and_login, web_login
from .test_reports import _buy, _sell
from .test_web_reports import HX, _csv, _txn

USER_ID = "fifo-user"


async def _two_parcels_one_sell(client, headers) -> dict:
    """Buy 100 @ 40 then 100 @ 50, sell 150 @ 60 less 10 fees in FY2024.

    FIFO:    cost 100 × 40 + 50 × 50 = 6,500 → gain 8,990 - 6,500 = 2,490; 50 left @ 50.
    Average: cost 150 × 45 = 6,750        → gain 8,990 - 6,750 = 2,240; 50 left @ 45.
    """
    stock = await create_stock(client)
    await _buy(client, stock["id"], headers, units=100, price=40, date="2024-07-10")
    await _buy(client, stock["id"], headers, units=100, price=50, date="2024-08-10")
    await _sell(client, stock["id"], headers, units=150, price=60, date="2025-01-15", fees=10)
    return stock


class TestCapitalGainsApi:
    async def test_a_sell_spanning_two_parcels_under_fifo(self, client):
        headers = await register_and_login(client, USER_ID)
        await _two_parcels_one_sell(client, headers)
        resp = await client.get("/api/reports/capital-gains", params={"fy": 2024, "method": "fifo"},
                                headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["method"] == "fifo"
        item = body["items"][0]
        assert item["units_sold"] == pytest.approx(150)
        assert item["avg_cost_basis"] == pytest.approx(6500 / 150)
        assert item["proceeds"] == pytest.approx(8990)
        assert item["gain_loss"] == pytest.approx(2490)
        assert body["total_gain_loss"] == pytest.approx(2490)

    async def test_average_is_the_default_and_unchanged(self, client):
        headers = await register_and_login(client, USER_ID)
        await _two_parcels_one_sell(client, headers)
        default = (await client.get("/api/reports/capital-gains", params={"fy": 2024}, headers=headers)).json()
        explicit = (await client.get("/api/reports/capital-gains", params={"fy": 2024, "method": "average"},
                                     headers=headers)).json()
        assert default == explicit
        assert default["method"] == "average"
        assert default["items"][0]["avg_cost_basis"] == pytest.approx(45)
        assert default["total_gain_loss"] == pytest.approx(2240)

    async def test_an_earlier_fy_sell_uses_up_the_oldest_parcel(self, client):
        """Buy 100 @ 10, sell 80 (FY2023); buy 100 @ 50, sell 100 @ 60 (FY2024).
        FIFO's FY2024 sell takes the 20 left @ 10, then 80 @ 50: cost 4,200."""
        headers = await register_and_login(client, USER_ID)
        stock = await create_stock(client)
        await _buy(client, stock["id"], headers, units=100, price=10, date="2023-08-01")
        await _sell(client, stock["id"], headers, units=80, price=20, date="2024-01-10")
        await _buy(client, stock["id"], headers, units=100, price=50, date="2024-08-01")
        await _sell(client, stock["id"], headers, units=100, price=60, date="2025-01-10")
        fifo = (await client.get("/api/reports/capital-gains", params={"fy": 2024, "method": "fifo"},
                                 headers=headers)).json()
        assert fifo["total_gain_loss"] == pytest.approx(6000 - 4200)
        # Average costs it at (1,000 + 5,000) / 200 = 30 a unit, as before.
        average = (await client.get("/api/reports/capital-gains", params={"fy": 2024}, headers=headers)).json()
        assert average["total_gain_loss"] == pytest.approx(6000 - 3000)

    async def test_a_same_day_buy_counts_before_the_sell(self, client):
        headers = await register_and_login(client, USER_ID)
        stock = await create_stock(client)
        await _sell(client, stock["id"], headers, units=10, price=30, date="2024-09-01")
        await _buy(client, stock["id"], headers, units=10, price=20, date="2024-09-01")
        fifo = (await client.get("/api/reports/capital-gains", params={"fy": 2024, "method": "fifo"},
                                 headers=headers)).json()
        assert fifo["total_gain_loss"] == pytest.approx(100)

    async def test_units_sold_beyond_those_held_cost_nothing(self, client):
        headers = await register_and_login(client, USER_ID)
        stock = await create_stock(client)
        await _buy(client, stock["id"], headers, units=10, price=20, date="2024-08-01")
        await _sell(client, stock["id"], headers, units=15, price=30, date="2024-09-01")
        fifo = (await client.get("/api/reports/capital-gains", params={"fy": 2024, "method": "fifo"},
                                 headers=headers)).json()
        assert fifo["total_gain_loss"] == pytest.approx(450 - 200)

    async def test_an_unknown_method_is_rejected(self, client):
        headers = await register_and_login(client, USER_ID)
        resp = await client.get("/api/reports/capital-gains", params={"fy": 2024, "method": "lifo"},
                                headers=headers)
        assert resp.status_code == 422


class TestHoldingsApi:
    async def test_fifo_costs_the_parcels_still_held(self, client):
        headers = await register_and_login(client, USER_ID)
        await _two_parcels_one_sell(client, headers)
        resp = await client.get("/api/reports/holdings", params={"as_of": "2025-06-30", "method": "fifo"},
                                headers=headers)
        body = resp.json()
        assert body["method"] == "fifo"
        assert body["holdings"][0]["units_held"] == pytest.approx(50)
        assert body["holdings"][0]["avg_cost_basis"] == pytest.approx(50)

    async def test_average_is_unchanged(self, client):
        headers = await register_and_login(client, USER_ID)
        await _two_parcels_one_sell(client, headers)
        body = (await client.get("/api/reports/holdings", params={"as_of": "2025-06-30"}, headers=headers)).json()
        assert body["method"] == "average"
        assert body["holdings"][0]["avg_cost_basis"] == pytest.approx(45)

    async def test_no_transactions_still_reports_the_method(self, client):
        headers = await register_and_login(client, USER_ID)
        body = (await client.get("/api/reports/holdings", params={"method": "fifo"}, headers=headers)).json()
        assert body == {"as_of": body["as_of"], "method": "fifo", "holdings": []}


async def _web_seed(client):
    bhp = await create_stock(client)
    await _txn(client, bhp["id"], "Buy", "100", "40", "2024-07-10")
    await _txn(client, bhp["id"], "Buy", "100", "50", "2024-08-10")
    await _txn(client, bhp["id"], "Sell", "150", "60", "2025-01-15", fees="10")


class TestWeb:
    async def test_gains_pane_picks_the_method(self, client):
        await web_login(client, "web-fifo")
        await _web_seed(client)
        resp = await client.get("/reports/gains", headers=HX, params={"fy": "2024", "method": "fifo"})
        assert resp.status_code == 200
        assert 'id="gains-method"' in resp.text
        assert '<option value="fifo" selected>FIFO</option>' in resp.text
        assert "2,490.00" in resp.text
        assert "FIFO cost basis" in resp.text
        assert 'href="/reports/gains.csv?fy=2024&amp;method=fifo"' in resp.text

    async def test_gains_pane_defaults_to_average(self, client):
        await web_login(client, "web-fifo")
        await _web_seed(client)
        for method in (None, "bogus"):
            params = {"fy": "2024"} | ({"method": method} if method else {})
            resp = await client.get("/reports/gains", headers=HX, params=params)
            assert '<option value="average" selected>Average</option>' in resp.text
            assert "2,240.00" in resp.text
            assert 'href="/reports/gains.csv?fy=2024"' in resp.text

    async def test_holdings_pane_picks_the_method(self, client):
        await web_login(client, "web-fifo")
        await _web_seed(client)
        resp = await client.get("/reports/holdings", headers=HX, params={"as_of": "2025-06-30", "method": "fifo"})
        assert 'id="holdings-method"' in resp.text
        assert "2,500.00" in resp.text  # cost base 50 × 50
        assert 'href="/reports/holdings.csv?as_of=2025-06-30&amp;method=fifo"' in resp.text

    async def test_csv_exports_honour_the_method(self, client):
        await web_login(client, "web-fifo")
        await _web_seed(client)
        resp = await client.get("/reports/gains.csv", params={"fy": "2024", "method": "fifo"})
        assert "pyfinbot-gains-fy2024-fifo.csv" in resp.headers["content-disposition"]
        assert float(_csv(resp)[1][6]) == pytest.approx(2490)
        resp = await client.get("/reports/holdings.csv", params={"as_of": "2025-06-30", "method": "fifo"})
        assert "pyfinbot-holdings-2025-06-30-fifo.csv" in resp.headers["content-disposition"]
        assert float(_csv(resp)[1][4]) == pytest.approx(50)
        resp = await client.get("/reports/gains.csv", params={"fy": "2024"})
        assert "pyfinbot-gains-fy2024.csv" in resp.headers["content-disposition"]
        assert float(_csv(resp)[1][6]) == pytest.approx(2240)
