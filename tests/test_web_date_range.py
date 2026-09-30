"""The transactions filter bar's gth_date_range (gth-ui v0.11.0 adoption)."""
from .conftest import create_stock, web_login
from .test_web_transactions import HX, _add


class TestDateRangeFilter:
    async def test_renders_the_component_with_july_fy(self, client):
        await web_login(client, "web-date-range")
        resp = await client.get("/transactions")
        html = resp.text
        assert "data-gth-date-range" in html and 'data-fy-start-month="7"' in html
        assert 'name="date_from"' in html and 'name="date_to"' in html
        for preset in ("today", "month", "fy", "last_fy"):
            assert f'data-preset="{preset}"' in html
        assert '<script src="/gth-assets/js/date-range.js"></script>' in html
        assert 'id="txn-from"' not in html  # the hand-built inputs are gone

    async def test_echoes_the_current_range(self, client):
        await web_login(client, "web-date-range")
        resp = await client.get("/transactions", params={"date_from": "2024-07-01", "date_to": "2025-06-30"})
        assert 'value="2024-07-01"' in resp.text and 'value="2025-06-30"' in resp.text

    async def test_a_financial_year_range_filters_the_table(self, client):
        await web_login(client, "web-date-range")
        bhp = await create_stock(client)
        await _add(client, bhp["id"], notes="fy23-buy", transaction_date="2024-06-30")
        await _add(client, bhp["id"], notes="fy24-buy", transaction_date="2024-07-01")
        await _add(client, bhp["id"], notes="fy24-sell", type="Sell", transaction_date="2025-06-30")
        await _add(client, bhp["id"], notes="fy25-buy", transaction_date="2025-07-01")
        # What the "This FY" chip submits on a day in FY2024 (1 Jul 2024 – 30 Jun 2025).
        resp = await client.get("/transactions", headers=HX,
                                params={"date_from": "2024-07-01", "date_to": "2025-06-30"})
        assert "fy24-buy" in resp.text and "fy24-sell" in resp.text
        assert "fy23-buy" not in resp.text and "fy25-buy" not in resp.text
