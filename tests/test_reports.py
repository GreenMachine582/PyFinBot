"""Integration tests for /api/reports endpoints."""
import pytest

from .conftest import register_and_login

USER_ID = "report-user"
OTHER_USER_ID = "other-user"


async def _create_stock(client, symbol="BHP", market="ASX", name="BHP Group"):
    resp = await client.post("/api/stocks/", json={"symbol": symbol, "market": market, "name": name})
    assert resp.status_code == 201
    return resp.json()


async def _buy(client, stock_id, headers, units, price, date="2024-08-01", fees=0):
    payload = {"stock_id": stock_id, "type": "Buy", "units": units,
               "price": price, "fees": fees, "transaction_date": date}
    resp = await client.post("/api/transactions/", json=payload, headers=headers)
    assert resp.status_code == 201
    return resp.json()


async def _sell(client, stock_id, headers, units, price, date="2025-01-01", fees=0):
    payload = {"stock_id": stock_id, "type": "Sell", "units": units,
               "price": price, "fees": fees, "transaction_date": date}
    resp = await client.post("/api/transactions/", json=payload, headers=headers)
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Holdings
# ---------------------------------------------------------------------------

class TestHoldings:
    async def test_no_token_returns_401(self, client):
        resp = await client.get("/api/reports/holdings")
        assert resp.status_code == 401

    async def test_empty_when_no_transactions(self, client):
        headers = await register_and_login(client, USER_ID)
        resp = await client.get("/api/reports/holdings", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["holdings"] == []

    async def test_buy_appears_in_holdings(self, client):
        headers = await register_and_login(client, USER_ID)
        stock = await _create_stock(client)
        await _buy(client, stock["id"], headers, units=10, price=25)
        resp = await client.get("/api/reports/holdings", headers=headers)
        assert resp.status_code == 200
        holdings = resp.json()["holdings"]
        assert len(holdings) == 1
        assert holdings[0]["symbol"] == "BHP"
        assert holdings[0]["units_held"] == pytest.approx(10)
        assert holdings[0]["avg_cost_basis"] == pytest.approx(25)

    async def test_partial_sell_reduces_units(self, client):
        headers = await register_and_login(client, USER_ID)
        stock = await _create_stock(client)
        await _buy(client, stock["id"], headers, units=10, price=25, date="2024-08-01")
        await _sell(client, stock["id"], headers, units=4, price=30, date="2024-09-01")
        resp = await client.get("/api/reports/holdings", headers=headers)
        holdings = resp.json()["holdings"]
        assert len(holdings) == 1
        assert holdings[0]["units_held"] == pytest.approx(6)

    async def test_full_sell_excluded_from_holdings(self, client):
        headers = await register_and_login(client, USER_ID)
        stock = await _create_stock(client)
        await _buy(client, stock["id"], headers, units=10, price=25, date="2024-08-01")
        await _sell(client, stock["id"], headers, units=10, price=30, date="2024-09-01")
        resp = await client.get("/api/reports/holdings", headers=headers)
        assert resp.json()["holdings"] == []

    async def test_as_of_date_excludes_future_transactions(self, client):
        headers = await register_and_login(client, USER_ID)
        stock = await _create_stock(client)
        await _buy(client, stock["id"], headers, units=10, price=25, date="2024-08-01")
        await _buy(client, stock["id"], headers, units=5, price=30, date="2025-06-01")
        resp = await client.get("/api/reports/holdings",
                                params={"as_of": "2024-12-31"}, headers=headers)
        holdings = resp.json()["holdings"]
        assert holdings[0]["units_held"] == pytest.approx(10)  # second buy not included

    async def test_avg_cost_basis_weighted(self, client):
        headers = await register_and_login(client, USER_ID)
        stock = await _create_stock(client)
        # 10 @ $20 + 10 @ $30 → avg = $25
        await _buy(client, stock["id"], headers, units=10, price=20, date="2024-08-01")
        await _buy(client, stock["id"], headers, units=10, price=30, date="2024-09-01")
        resp = await client.get("/api/reports/holdings", headers=headers)
        holdings = resp.json()["holdings"]
        assert holdings[0]["avg_cost_basis"] == pytest.approx(25)

    async def test_only_requesting_users_holdings(self, client):
        headers = await register_and_login(client, USER_ID)
        other_headers = await register_and_login(client, OTHER_USER_ID)
        stock = await _create_stock(client)
        await _buy(client, stock["id"], headers, units=10, price=25)
        # Other user buys same stock
        other_payload = {"stock_id": stock["id"], "type": "Buy", "units": 999, "price": 1}
        await client.post("/api/transactions/", json=other_payload, headers=other_headers)

        resp = await client.get("/api/reports/holdings", headers=headers)
        holdings = resp.json()["holdings"]
        assert len(holdings) == 1
        assert holdings[0]["units_held"] == pytest.approx(10)


# ---------------------------------------------------------------------------
# Capital Gains
# ---------------------------------------------------------------------------

class TestCapitalGains:
    async def test_no_token_returns_401(self, client):
        resp = await client.get("/api/reports/capital-gains", params={"fy": 2024})
        assert resp.status_code == 401

    async def test_no_sells_returns_zero(self, client):
        headers = await register_and_login(client, USER_ID)
        stock = await _create_stock(client)
        await _buy(client, stock["id"], headers, units=10, price=25)
        resp = await client.get("/api/reports/capital-gains",
                                params={"fy": 2024}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_gain_loss"] == 0.0
        assert data["items"] == []

    async def test_simple_gain(self, client):
        headers = await register_and_login(client, USER_ID)
        stock = await _create_stock(client)
        # Buy 10 @ $20 (FY2024: Aug 2024)
        await _buy(client, stock["id"], headers, units=10, price=20, date="2024-08-01")
        # Sell 10 @ $30 (FY2024: Jan 2025)
        await _sell(client, stock["id"], headers, units=10, price=30, date="2025-01-01")

        resp = await client.get("/api/reports/capital-gains",
                                params={"fy": 2024}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["symbol"] == "BHP"
        assert item["proceeds"] == pytest.approx(300)
        assert item["avg_cost_basis"] == pytest.approx(20)
        assert item["gain_loss"] == pytest.approx(100)  # 300 - 200
        assert data["total_gain_loss"] == pytest.approx(100)

    async def test_sell_with_fees_reduces_proceeds(self, client):
        headers = await register_and_login(client, USER_ID)
        stock = await _create_stock(client)
        await _buy(client, stock["id"], headers, units=10, price=20, date="2024-08-01")
        await _sell(client, stock["id"], headers, units=10, price=30, date="2025-01-01", fees=9.95)

        resp = await client.get("/api/reports/capital-gains",
                                params={"fy": 2024}, headers=headers)
        item = resp.json()["items"][0]
        assert item["proceeds"] == pytest.approx(290.05)
        assert item["gain_loss"] == pytest.approx(90.05)

    async def test_loss_is_negative(self, client):
        headers = await register_and_login(client, USER_ID)
        stock = await _create_stock(client)
        await _buy(client, stock["id"], headers, units=10, price=30, date="2024-08-01")
        await _sell(client, stock["id"], headers, units=10, price=20, date="2025-01-01")

        resp = await client.get("/api/reports/capital-gains",
                                params={"fy": 2024}, headers=headers)
        assert resp.json()["total_gain_loss"] == pytest.approx(-100)

    async def test_sells_in_wrong_fy_excluded(self, client):
        headers = await register_and_login(client, USER_ID)
        stock = await _create_stock(client)
        await _buy(client, stock["id"], headers, units=10, price=20, date="2023-08-01")
        # This sell is in FY2023 (Jan 2024), not FY2024
        await _sell(client, stock["id"], headers, units=5, price=30, date="2024-01-01")

        resp = await client.get("/api/reports/capital-gains",
                                params={"fy": 2024}, headers=headers)
        assert resp.json()["items"] == []

    async def test_multiple_stocks_reported_separately(self, client):
        headers = await register_and_login(client, USER_ID)
        bhp = await _create_stock(client, "BHP")
        cba = await _create_stock(client, "CBA", name="Commonwealth Bank")
        await _buy(client, bhp["id"], headers, units=10, price=20, date="2024-08-01")
        await _buy(client, cba["id"], headers, units=5, price=100, date="2024-08-01")
        await _sell(client, bhp["id"], headers, units=10, price=30, date="2025-01-01")
        await _sell(client, cba["id"], headers, units=5, price=80, date="2025-01-01")

        resp = await client.get("/api/reports/capital-gains",
                                params={"fy": 2024}, headers=headers)
        data = resp.json()
        assert len(data["items"]) == 2
        symbols = {i["symbol"] for i in data["items"]}
        assert symbols == {"BHP", "CBA"}
        # BHP: gain=100, CBA: loss=-100 → net 0
        assert data["total_gain_loss"] == pytest.approx(0)
