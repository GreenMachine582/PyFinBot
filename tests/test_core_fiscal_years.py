"""Fiscal years come from greentechhub_core.dates: fiscal_year replaces
core/fiscal_year.au_fiscal_year, fiscal_year_bounds the hand-built FY end,
and fiscal_year_label the |fy filter. Same rule as before: FY N runs
1 Jul N to 30 Jun N+1."""
import importlib.util

import pytest
from greentechhub_core.dates import fiscal_year_label

from pyfinbot.web.templating import templates

from .conftest import create_stock, register_and_login


def test_hand_rolled_fiscal_year_module_is_gone():
    assert importlib.util.find_spec("pyfinbot.core.fiscal_year") is None


def test_fy_filter_is_cores_label():
    fy = templates.env.filters["fy"]
    assert fy is fiscal_year_label
    assert (fy(2024), fy(1999)) == ("2024–25", "1999–00")
    assert templates.env.filters["fy_options"]([2025, 2024]) == [(2025, "2025–26"), (2024, "2024–25")]


async def _add(client, headers, stock_id, type_, day, units=10, price=20):
    resp = await client.post("/api/transactions/", headers=headers, json={
        "stock_id": stock_id, "type": type_, "units": units, "price": price, "fees": 0,
        "transaction_date": day})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_30_june_and_1_july_fall_in_different_years(client):
    headers = await register_and_login(client, "fy-boundary")
    stock = await create_stock(client, "FYB", "ASX", "FY Boundary")
    assert (await _add(client, headers, stock["id"], "Buy", "2025-06-30"))["fy"] == 2024
    assert (await _add(client, headers, stock["id"], "Buy", "2025-07-01"))["fy"] == 2025


async def test_gains_for_a_year_end_on_30_june(client):
    headers = await register_and_login(client, "fy-gains")
    stock = await create_stock(client, "FYG", "ASX", "FY Gains")
    await _add(client, headers, stock["id"], "Buy", "2024-08-01", units=20, price=20)
    await _add(client, headers, stock["id"], "Sell", "2025-06-30", units=10, price=30)  # last day of FY 2024
    await _add(client, headers, stock["id"], "Sell", "2025-07-01", units=10, price=40)  # FY 2025

    fy2024 = (await client.get("/api/reports/capital-gains", params={"fy": 2024}, headers=headers)).json()
    assert [i["proceeds"] for i in fy2024["items"]] == [pytest.approx(300)]
    fy2025 = (await client.get("/api/reports/capital-gains", params={"fy": 2025}, headers=headers)).json()
    assert [i["proceeds"] for i in fy2025["items"]] == [pytest.approx(400)]
