"""Integration tests for the /transactions web pages."""
import re

from httpx import AsyncClient

from .conftest import create_stock, hx_triggers, web_login

HX = {"HX-Request": "true"}


def _checked_type(html: str) -> str | None:
    """Which Buy/Sell toggle radio the form renders as checked."""
    checked = [m.group(1) for m in re.finditer(r'<input type="radio"[^>]*value="(\w+)"[^>]*>', html)
               if " checked" in m.group(0)]
    assert len(checked) <= 1
    return checked[0] if checked else None


def _form(stock_id, **overrides) -> dict:
    return {
        "stock_id": str(stock_id),
        "transaction_date": "2024-08-01",
        "type": "Buy",
        "units": "10",
        "price": "25.5",
        "fees": "9.95",
        "notes": "",
        **overrides,
    }


async def _add(client: AsyncClient, stock_id, **overrides) -> None:
    resp = await client.post("/transactions", data=_form(stock_id, **overrides))
    assert resp.status_code == 204, resp.text


async def _only_transaction_id(client: AsyncClient, user_id: str) -> int:
    """The web layer never returns ids as JSON, so read them back via the
    API with a bearer token for the same user."""
    resp = await client.post("/api/auth/login", data={"username": user_id, "password": "hunter2!"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    items = (await client.get("/api/transactions/", headers=headers)).json()["items"]
    assert len(items) == 1
    return items[0]["id"]


async def _api_get(client: AsyncClient, user_id: str, transaction_id: int) -> dict:
    resp = await client.post("/api/auth/login", data={"username": user_id, "password": "hunter2!"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    return (await client.get(f"/api/transactions/{transaction_id}", headers=headers)).json()


class TestAuthGuard:
    async def test_page_redirects_to_login(self, client):
        resp = await client.get("/transactions", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/login"

    async def test_htmx_request_gets_hx_redirect(self, client):
        resp = await client.post("/transactions", headers=HX, data={}, follow_redirects=False)
        assert resp.status_code == 401
        assert resp.headers["HX-Redirect"] == "/login"


class TestCreate:
    async def test_new_form_renders_combobox_and_defaults_to_buy(self, client):
        await web_login(client, "web-txn")
        resp = await client.get("/transactions/new")
        assert resp.status_code == 200
        assert "New transaction" in resp.text
        assert 'role="combobox"' in resp.text
        assert '<input type="hidden" name="stock_id" value=""' in resp.text
        assert _checked_type(resp.text) == "Buy"

    async def test_create_computes_derived_fields(self, client):
        await web_login(client, "web-txn")
        stock = await create_stock(client)
        resp = await client.post("/transactions", data=_form(stock["id"], notes="first buy"))
        assert resp.status_code == 204
        triggers = hx_triggers(resp)
        assert triggers["showToast"]["message"] == "Added Buy BHP"
        assert triggers["closeModal"] and triggers["transactionsChanged"]

        txn = await _api_get(client, "web-txn", await _only_transaction_id(client, "web-txn"))
        assert txn["total_value"] == 255.0
        assert txn["cost"] == -264.95
        assert txn["notes"] == "first buy"
        assert txn["user_id"] == "web-txn"

    async def test_missing_fields_rerender_with_422(self, client):
        await web_login(client, "web-txn")
        resp = await client.post("/transactions", data=_form("", units="", transaction_date=""))
        assert resp.status_code == 422
        assert "Choose a stock." in resp.text
        assert "Enter a date." in resp.text
        assert "This field is required." in resp.text

    async def test_invalid_values_rerender_with_422(self, client):
        await web_login(client, "web-txn")
        stock = await create_stock(client)
        resp = await client.post("/transactions", data=_form(stock["id"], units="0", price="-1", fees="-2"))
        assert resp.status_code == 422
        assert "Must be greater than 0." in resp.text
        assert resp.text.count("Can&#39;t be negative.") == 2

    async def test_unparseable_values_rerender_with_422(self, client):
        await web_login(client, "web-txn")
        stock = await create_stock(client)
        resp = await client.post("/transactions", data=_form(stock["id"], units="lots"))
        assert resp.status_code == 422
        assert "is-invalid" in resp.text

    async def test_search_text_is_kept_when_no_stock_picked(self, client):
        await web_login(client, "web-txn")
        resp = await client.post("/transactions", data=_form("", stock_id_search="bh", type="Sell"))
        assert resp.status_code == 422
        assert 'value="bh"' in resp.text
        assert _checked_type(resp.text) == "Sell"

    async def test_unknown_stock_is_a_field_error(self, client):
        await web_login(client, "web-txn")
        resp = await client.post("/transactions", data=_form(999999))
        assert resp.status_code == 422
        assert "Choose a stock." in resp.text


class TestList:
    async def test_rows_show_resolved_stock_and_only_own_transactions(self, client):
        await web_login(client, "web-other")
        stock = await create_stock(client)
        await _add(client, stock["id"], notes="not yours")

        await web_login(client, "web-txn")
        await _add(client, stock["id"], notes="mine")

        resp = await client.get("/transactions")
        assert resp.status_code == 200
        assert "BHP</span> · ASX" in resp.text
        assert "mine" in resp.text
        assert "not yours" not in resp.text
        assert "2024–25" in resp.text  # FY 2024 = 1 Jul 2024 – 30 Jun 2025
        assert 'aria-sort="descending"' in resp.text  # newest first by default
        assert "gth-badge" in resp.text and "Buy</span>" in resp.text

    async def test_filters(self, client):
        await web_login(client, "web-txn")
        bhp = await create_stock(client, "BHP")
        cba = await create_stock(client, "CBA", name="Commonwealth Bank")
        await _add(client, bhp["id"], notes="bhp-buy", transaction_date="2023-08-01")
        await _add(client, cba["id"], notes="cba-sell", type="Sell", transaction_date="2024-08-01")

        resp = await client.get("/transactions", headers=HX, params={"stock": "cba"})
        assert "cba-sell" in resp.text and "bhp-buy" not in resp.text

        resp = await client.get("/transactions", headers=HX, params={"type": "Buy"})
        assert "bhp-buy" in resp.text and "cba-sell" not in resp.text

        resp = await client.get("/transactions", headers=HX, params={"fy": "2024"})
        assert "cba-sell" in resp.text and "bhp-buy" not in resp.text

        resp = await client.get("/transactions", headers=HX, params={"date_from": "2024-01-01"})
        assert "cba-sell" in resp.text and "bhp-buy" not in resp.text

        resp = await client.get("/transactions", headers=HX, params={"date_to": "2024-01-01", "date_from": "not-a-date"})
        assert "bhp-buy" in resp.text and "cba-sell" not in resp.text

        resp = await client.get("/transactions", headers=HX, params={"sort": "transaction_date", "dir": "asc"})
        assert resp.text.index("bhp-buy") < resp.text.index("cba-sell")

    async def test_empty_state(self, client):
        await web_login(client, "web-txn")
        resp = await client.get("/transactions", headers=HX)
        assert "No transactions match these filters." in resp.text


class TestEdit:
    async def test_edit_form_prefills(self, client):
        await web_login(client, "web-txn")
        stock = await create_stock(client)
        await _add(client, stock["id"])
        transaction_id = await _only_transaction_id(client, "web-txn")

        resp = await client.get(f"/transactions/{transaction_id}/edit")
        assert resp.status_code == 200
        assert "Edit transaction" in resp.text
        assert 'value="25.5"' in resp.text and 'value="9.95"' in resp.text
        assert f'<input type="hidden" name="stock_id" value="{stock["id"]}"' in resp.text
        assert 'value="BHP · ASX — BHP Group"' in resp.text
        assert _checked_type(resp.text) == "Buy"

    async def test_full_edit_recomputes(self, client):
        await web_login(client, "web-txn")
        bhp = await create_stock(client, "BHP")
        cba = await create_stock(client, "CBA", name="Commonwealth Bank")
        await _add(client, bhp["id"], transaction_date="2024-06-30")
        transaction_id = await _only_transaction_id(client, "web-txn")
        before = await _api_get(client, "web-txn", transaction_id)

        resp = await client.post(f"/transactions/{transaction_id}", data=_form(
            cba["id"], type="Sell", units="4", price="100", fees="10", transaction_date="2024-07-01",
        ))
        assert resp.status_code == 204
        assert hx_triggers(resp)["showToast"]["message"] == "Saved Sell CBA"

        after = await _api_get(client, "web-txn", transaction_id)
        assert after["stock"]["symbol"] == "CBA"
        assert after["total_value"] == 400.0
        assert after["cost"] == 390.0  # sell: +total - fees
        assert after["fy"] == before["fy"] + 1  # crossed 30 June

    async def test_invalid_edit_rerenders_with_422(self, client):
        await web_login(client, "web-txn")
        stock = await create_stock(client)
        await _add(client, stock["id"])
        transaction_id = await _only_transaction_id(client, "web-txn")
        resp = await client.post(f"/transactions/{transaction_id}", data=_form(stock["id"], units=""))
        assert resp.status_code == 422
        assert "This field is required." in resp.text
        assert f'hx-post="/transactions/{transaction_id}"' in resp.text  # still the edit form

    async def test_other_users_transaction_is_404(self, client):
        await web_login(client, "web-owner")
        stock = await create_stock(client)
        await _add(client, stock["id"])
        transaction_id = await _only_transaction_id(client, "web-owner")

        await web_login(client, "web-intruder")
        assert (await client.get(f"/transactions/{transaction_id}/edit")).status_code == 404
        assert (await client.post(f"/transactions/{transaction_id}", data=_form(stock["id"]))).status_code == 404
        assert (await client.get(f"/transactions/{transaction_id}/delete")).status_code == 404
        assert (await client.delete(f"/transactions/{transaction_id}")).status_code == 404


class TestDelete:
    async def test_confirm_then_delete(self, client):
        await web_login(client, "web-txn")
        stock = await create_stock(client)
        await _add(client, stock["id"])
        transaction_id = await _only_transaction_id(client, "web-txn")

        resp = await client.get(f"/transactions/{transaction_id}/delete")
        assert resp.status_code == 200
        assert "Delete this Buy of BHP?" in resp.text

        resp = await client.delete(f"/transactions/{transaction_id}")
        assert resp.status_code == 204
        assert hx_triggers(resp)["showToast"]["message"] == "Deleted Buy BHP"
        assert "No transactions match these filters." in (await client.get("/transactions", headers=HX)).text
