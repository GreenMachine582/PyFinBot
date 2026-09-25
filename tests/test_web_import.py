"""Integration tests for the /import web page."""
import io

from httpx import AsyncClient

from .conftest import create_stock, hx_triggers, web_login

HX = {"HX-Request": "true"}
CSV_HEADER = "date,stock,type,units,price,fees,notes\n"


def _upload(content: str, filename: str = "trades.csv") -> dict:
    return {"file": (filename, io.BytesIO(content.encode()), "text/csv")}


async def _api_transactions(client: AsyncClient, user_id: str) -> list[dict]:
    """The web layer never returns transactions as JSON, so read them back
    via the API with a bearer token for the same user."""
    resp = await client.post("/api/auth/login", data={"username": user_id, "password": "hunter2!"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    return (await client.get("/api/transactions/", headers=headers)).json()["items"]


class TestAuthGuard:
    async def test_page_redirects_to_login(self, client):
        resp = await client.get("/import", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/login"

    async def test_htmx_upload_gets_hx_redirect(self, client):
        resp = await client.post("/import", files=_upload(CSV_HEADER), headers=HX, follow_redirects=False)
        assert resp.status_code == 401
        assert resp.headers["HX-Redirect"] == "/login"


class TestPage:
    async def test_renders_form_and_column_help(self, client):
        await web_login(client, "web-import")
        resp = await client.get("/import")
        assert resp.status_code == 200
        assert 'hx-encoding="multipart/form-data"' in resp.text
        assert 'accept=".csv,.xls,.xlsx,.xlsm"' in resp.text
        assert "<code>brokerage</code>" in resp.text  # an alias, from the shared alias map
        assert 'href="/import" aria-current="page"' in resp.text  # navbar marks the active page


class TestUpload:
    async def test_all_rows_imported(self, client):
        await web_login(client, "web-import")
        await create_stock(client)
        csv = (CSV_HEADER
               + "2024-08-01,ASX:BHP,Buy,10,25.50,9.95,First\n"
               + "02/08/2024,ASX:BHP,Sell,5,26.00,,\n")
        resp = await client.post("/import", files=_upload(csv), headers=HX)
        assert resp.status_code == 200
        assert "<html" not in resp.text  # the result fragment only
        assert "Results — trades.csv" in resp.text
        assert "2 imported" in resp.text and "0 skipped" in resp.text
        assert 'href="/transactions"' in resp.text
        triggers = hx_triggers(resp)
        assert triggers["showToast"]["kind"] == "success"
        assert triggers["showToast"]["message"] == "Imported 2 transactions."
        assert triggers["transactionsChanged"]

        items = await _api_transactions(client, "web-import")
        assert {t["notes"] for t in items} == {"First", None}

    async def test_imports_as_the_logged_in_user(self, client):
        await web_login(client, "web-import-a")
        await create_stock(client)
        await client.post("/import", files=_upload(CSV_HEADER + "2024-08-01,ASX:BHP,Buy,10,25.50,,\n"))
        await web_login(client, "web-import-b")
        assert len(await _api_transactions(client, "web-import-a")) == 1
        assert await _api_transactions(client, "web-import-b") == []

    async def test_bad_rows_are_listed(self, client):
        await web_login(client, "web-import")
        await create_stock(client)
        csv = (CSV_HEADER
               + "2024-08-01,ASX:BHP,Buy,10,25.50,,\n"
               + "2024-08-02,ASX:NOPE,Buy,1,1.00,,\n"
               + "2024-08-03,ASX:BHP,Hold,1,1.00,,\n"
               + "2024-08-04,ASX:BHP,Buy,lots,1.00,,\n")
        resp = await client.post("/import", files=_upload(csv))
        assert resp.status_code == 200
        assert "1 imported" in resp.text and "3 skipped" in resp.text
        assert "<td class=\"text-nowrap\">3</td><td>Stock &#39;ASX:NOPE&#39; not found</td>" in resp.text
        assert "Invalid type &#39;Hold&#39;" in resp.text
        assert "must be numbers" in resp.text
        triggers = hx_triggers(resp)
        assert triggers["showToast"]["kind"] == "warning"
        assert triggers["showToast"]["message"] == "Imported 1 transaction; 3 skipped."
        assert triggers["transactionsChanged"]
        # The bad-number row after a good one mustn't roll the good one back.
        assert len(await _api_transactions(client, "web-import")) == 1

    async def test_reupload_imports_nothing(self, client):
        await web_login(client, "web-import")
        await create_stock(client)
        csv = CSV_HEADER + "2024-08-01,ASX:BHP,Buy,10,25.50,,\n"
        await client.post("/import", files=_upload(csv))
        resp = await client.post("/import", files=_upload(csv))
        assert "Duplicate transaction" in resp.text
        assert 'href="/transactions"' not in resp.text
        triggers = hx_triggers(resp)
        assert triggers["showToast"]["message"] == "Nothing imported; 1 skipped."
        assert "transactionsChanged" not in triggers

    async def test_header_only_file(self, client):
        await web_login(client, "web-import")
        resp = await client.post("/import", files=_upload(CSV_HEADER))
        assert resp.status_code == 200
        triggers = hx_triggers(resp)
        assert triggers["showToast"]["kind"] == "info"
        assert "transactionsChanged" not in triggers


class TestFileErrors:
    async def test_missing_columns(self, client):
        await web_login(client, "web-import")
        resp = await client.post("/import", files=_upload("date,stock\n2024-08-01,ASX:BHP\n", "short.csv"))
        assert resp.status_code == 422
        assert "Couldn't import short.csv" in resp.text
        assert "Missing required columns" in resp.text
        triggers = hx_triggers(resp)
        assert triggers["showToast"]["kind"] == "danger"
        assert triggers["showToast"]["title"] == "Import failed"

    async def test_empty_file(self, client):
        await web_login(client, "web-import")
        resp = await client.post("/import", files=_upload(""))
        assert resp.status_code == 422
        assert "Uploaded file is empty" in resp.text

    async def test_no_file_chosen(self, client):
        await web_login(client, "web-import")
        resp = await client.post("/import", data={})
        assert resp.status_code == 422
        assert "Uploaded file is empty" in resp.text
