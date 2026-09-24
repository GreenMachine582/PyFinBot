"""Integration tests for the /stocks web pages."""
from unittest.mock import AsyncMock, patch


from pyfinbot.core.market_sync import market_sync_guard

from .conftest import create_stock, hx_triggers, register_and_login, web_login

HX = {"HX-Request": "true"}


class TestAuthGuard:
    async def test_page_redirects_to_login(self, client):
        resp = await client.get("/stocks", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/login"

    async def test_htmx_request_gets_hx_redirect(self, client):
        resp = await client.get("/stocks/rows", headers=HX, follow_redirects=False)
        assert resp.status_code == 401
        assert resp.headers["HX-Redirect"] == "/login"


class TestList:
    async def test_page_renders_active_stocks(self, client):
        await web_login(client, "web-stocks")
        await create_stock(client, "BHP", name="BHP Group")
        archived = await create_stock(client, "OLD", name="Old Co")
        await client.put(f"/api/stocks/{archived['id']}", json={"is_active": False})

        resp = await client.get("/stocks")
        assert resp.status_code == 200
        assert "BHP Group" in resp.text
        assert "Old Co" not in resp.text  # default filter is Active
        assert "Sync ASX" in resp.text
        assert 'data-gth-start-toast="ASX sync started' in resp.text
        assert 'href="/stocks" aria-current="page"' in resp.text  # navbar marks the active page

    async def test_filters(self, client):
        await web_login(client, "web-stocks")
        await create_stock(client, "BHP", name="BHP Group")
        await create_stock(client, "CBA", name="Commonwealth Bank")
        await create_stock(client, "AAPL", market="NASDAQ", name="Apple")
        archived = await create_stock(client, "OLD", name="Old Co")
        await client.put(f"/api/stocks/{archived['id']}", json={"is_active": False})

        resp = await client.get("/stocks/rows", params={"q": "common"})
        assert "Commonwealth Bank" in resp.text and "BHP Group" not in resp.text

        resp = await client.get("/stocks/rows", params={"market": "NASDAQ"})
        assert "Apple" in resp.text and "BHP Group" not in resp.text

        resp = await client.get("/stocks/rows", params={"status": "archived"})
        assert "Old Co" in resp.text and "BHP Group" not in resp.text

        resp = await client.get("/stocks/rows", params={"status": "all", "sort": "-symbol"})
        assert resp.text.index("OLD") < resp.text.index("BHP")

    async def test_empty_state(self, client):
        await web_login(client, "web-stocks")
        resp = await client.get("/stocks/rows", params={"q": "zzz"})
        assert "No stocks match these filters." in resp.text

    async def test_load_more_paging(self, client):
        await web_login(client, "web-stocks")
        for symbol in ("AAA", "BBB", "CCC"):
            await create_stock(client, symbol, name=f"{symbol} Ltd")

        resp = await client.get("/stocks/rows", params={"size": 2, "q": "Ltd"})
        assert "AAA Ltd" in resp.text and "CCC Ltd" not in resp.text
        assert "/stocks/rows?q=Ltd" in resp.text and "page=2" in resp.text

        resp = await client.get("/stocks/rows", params={"size": 2, "page": 2, "q": "Ltd"})
        assert "CCC Ltd" in resp.text
        assert "Load more" not in resp.text


class TestCreate:
    async def test_new_form_renders(self, client):
        await web_login(client, "web-stocks")
        resp = await client.get("/stocks/new")
        assert resp.status_code == 200
        assert "New stock" in resp.text

    async def test_create(self, client):
        await web_login(client, "web-stocks")
        resp = await client.post("/stocks", data={"market": "asx", "symbol": "wes", "name": "Wesfarmers"})
        assert resp.status_code == 204
        triggers = hx_triggers(resp)
        assert triggers["showToast"]["message"] == "Added ASX:WES"
        assert triggers["closeModal"] and triggers["stocksChanged"]

        stock = (await client.get("/api/stocks/ASX:WES")).json()
        assert stock["name"] == "Wesfarmers"

    async def test_missing_fields_rerender_with_422(self, client):
        await web_login(client, "web-stocks")
        resp = await client.post("/stocks", data={"market": "ASX", "symbol": "", "name": ""})
        assert resp.status_code == 422
        assert resp.text.count("This field is required.") == 2
        assert 'value="ASX"' in resp.text  # input is preserved

    async def test_duplicate_is_a_field_error(self, client):
        await web_login(client, "web-stocks")
        await create_stock(client, "BHP")
        resp = await client.post("/stocks", data={"market": "ASX", "symbol": "bhp", "name": "Again"})
        assert resp.status_code == 422
        assert "ASX:BHP already exists." in resp.text


class TestEdit:
    async def test_edit_form_renders(self, client):
        await web_login(client, "web-stocks")
        stock = await create_stock(client)
        resp = await client.get(f"/stocks/{stock['id']}/edit")
        assert resp.status_code == 200
        assert "Edit ASX:BHP" in resp.text
        assert 'value="BHP Group"' in resp.text

    async def test_edit_missing_returns_404(self, client):
        await web_login(client, "web-stocks")
        resp = await client.get("/stocks/999999/edit")
        assert resp.status_code == 404

    async def test_rename_and_archive_then_reactivate(self, client):
        await web_login(client, "web-stocks")
        stock = await create_stock(client)

        resp = await client.post(f"/stocks/{stock['id']}", data={"name": "BHP Billiton"})
        assert resp.status_code == 204
        assert hx_triggers(resp)["showToast"]["message"] == "Saved ASX:BHP"
        updated = (await client.get(f"/api/stocks/{stock['id']}")).json()
        assert updated["name"] == "BHP Billiton"
        assert updated["is_active"] is False  # unticked checkbox = archive

        resp = await client.post(f"/stocks/{stock['id']}", data={"name": "BHP Billiton", "is_active": "on"})
        assert resp.status_code == 204
        assert (await client.get(f"/api/stocks/{stock['id']}")).json()["is_active"] is True

    async def test_blank_name_rerenders_with_422(self, client):
        await web_login(client, "web-stocks")
        stock = await create_stock(client)
        resp = await client.post(f"/stocks/{stock['id']}", data={"name": "  ", "is_active": "on"})
        assert resp.status_code == 422
        assert "This field is required." in resp.text


class TestDelete:
    async def test_confirm_modal_renders(self, client):
        await web_login(client, "web-stocks")
        stock = await create_stock(client)
        resp = await client.get(f"/stocks/{stock['id']}/delete")
        assert resp.status_code == 200
        assert "Delete ASX:BHP?" in resp.text

    async def test_delete(self, client):
        await web_login(client, "web-stocks")
        stock = await create_stock(client)
        resp = await client.delete(f"/stocks/{stock['id']}")
        assert resp.status_code == 204
        assert hx_triggers(resp)["showToast"]["message"] == "Deleted ASX:BHP"
        assert (await client.get(f"/api/stocks/{stock['id']}")).status_code == 404

    async def test_delete_blocked_when_transactions_exist(self, client):
        headers = await register_and_login(client, "api-user")
        await web_login(client, "web-stocks")
        stock = await create_stock(client)
        resp = await client.post("/api/transactions/", headers=headers, json={
            "stock_id": stock["id"], "type": "Buy", "units": 1, "price": 1, "transaction_date": "2024-08-01",
        })
        assert resp.status_code == 201

        resp = await client.delete(f"/stocks/{stock['id']}")
        assert resp.status_code == 204
        toast = hx_triggers(resp)["showToast"]
        assert toast["kind"] == "danger"
        assert "has 1 transaction — archive it instead." in toast["message"]
        assert (await client.get(f"/api/stocks/{stock['id']}")).status_code == 200


class TestOptions:
    async def test_matches_active_stocks_only(self, client):
        await web_login(client, "web-stocks")
        bhp = await create_stock(client, "BHP", name="BHP Group")
        archived = await create_stock(client, "BHPX", name="Old BHP")
        await client.put(f"/api/stocks/{archived['id']}", json={"is_active": False})

        resp = await client.get("/stocks/options", params={"q": "bhp"})
        assert f'data-value="{bhp["id"]}"' in resp.text
        assert 'data-label="BHP · ASX — BHP Group"' in resp.text
        assert "Old BHP" not in resp.text

    async def test_empty_query_lists_all_active(self, client):
        """Clearing the combobox's search text must bring the full list back."""
        await web_login(client, "web-stocks")
        await create_stock(client, "BHP", name="BHP Group")
        await create_stock(client, "CBA", name="Commonwealth Bank")
        resp = await client.get("/stocks/options", params={"q": ""})
        assert "BHP Group" in resp.text and "Commonwealth Bank" in resp.text

    async def test_no_matches(self, client):
        await web_login(client, "web-stocks")
        resp = await client.get("/stocks/options", params={"q": "zzz"})
        assert "No matching active stocks" in resp.text


class TestSync:
    async def test_sync_reports_counts(self, client):
        await web_login(client, "web-stocks")
        with patch("pyfinbot.web.routes.stocks.syncMarket",
                   new=AsyncMock(return_value=(["A", "B"], ["C"], []))) as sync:
            resp = await client.post("/stocks/sync/asx")
        assert resp.status_code == 204
        sync.assert_awaited_once()
        assert sync.await_args.args[1] == "ASX"
        triggers = hx_triggers(resp)
        assert triggers["showToast"]["message"] == "ASX sync: 2 created, 1 updated, 0 archived"
        assert triggers["stocksChanged"]

    async def test_already_running_is_refused(self, client):
        await web_login(client, "web-stocks")
        with patch("pyfinbot.web.routes.stocks.syncMarket", new=AsyncMock()) as sync:
            with market_sync_guard("ASX") as held:
                assert held
                resp = await client.post("/stocks/sync/ASX")
        sync.assert_not_awaited()
        toast = hx_triggers(resp)["showToast"]
        assert toast["kind"] == "warning"
        assert "already running" in toast["message"]

    async def test_unsupported_market(self, client):
        await web_login(client, "web-stocks")
        resp = await client.post("/stocks/sync/NYSE")
        assert hx_triggers(resp)["showToast"]["kind"] == "danger"

    async def test_failure_is_logged_and_toasted_without_internals(self, client, caplog):
        await web_login(client, "web-stocks")
        with patch("pyfinbot.web.routes.stocks.syncMarket",
                   new=AsyncMock(side_effect=RuntimeError("https://internal/offline"))):
            resp = await client.post("/stocks/sync/ASX")
        toast = hx_triggers(resp)["showToast"]
        assert toast["kind"] == "danger"
        assert toast["message"] == "ASX sync failed — see the server logs."
        assert "internal" not in toast["message"]
        assert "ASX market sync failed" in caplog.text

    async def test_lock_is_released_after_a_sync(self, client):
        await web_login(client, "web-stocks")
        with patch("pyfinbot.web.routes.stocks.syncMarket", new=AsyncMock(return_value=([], [], []))):
            await client.post("/stocks/sync/ASX")
            resp = await client.post("/stocks/sync/ASX")
        assert "already running" not in hx_triggers(resp)["showToast"]["message"]
