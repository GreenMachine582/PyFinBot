"""Form polish (greentechhub-ui v0.11 form-field extras): $ prefixes on
Price and Fees, notes as a 500-character textarea with a counter, and
maxlength on stock codes — each limit also enforced server-side, while the
CSV and Commsec importers truncate notes instead of failing the row."""
import dataclasses
import io
from unittest.mock import patch

from pyfinbot.core import commsec_import
from pyfinbot.models.stock_models import CODE_MAX
from pyfinbot.models.transaction_models import NOTES_MAX

from .conftest import create_stock, register_and_login, web_login
from .test_email_sync import _fake_messages

HX = {"HX-Request": "true"}


async def _api_items(client, headers):
    return (await client.get("/api/transactions/", headers=headers)).json()["items"]


def _form(stock_id, **overrides):
    return {"stock_id": str(stock_id), "transaction_date": "2024-08-01", "type": "Buy",
            "units": "10", "price": "25.5", "fees": "9.95", "notes": "", **overrides}


class TestTransactionForm:
    async def test_renders_prefixes_and_a_notes_textarea(self, client):
        await web_login(client, "polish-form")
        form = (await client.get("/transactions/new", headers=HX)).text
        assert form.count('<span class="input-group-text" id="gth-field-price-prefix">$</span>') == 1
        assert form.count('<span class="input-group-text" id="gth-field-fees-prefix">$</span>') == 1
        assert '<textarea rows="3" id="gth-field-notes" name="notes"' in form
        assert f'maxlength="{NOTES_MAX}"' in form and f"0 / {NOTES_MAX}" in form

    async def test_notes_over_the_limit_rerender_with_an_error(self, client):
        await web_login(client, "polish-long")
        stock = await create_stock(client, "PLN", "ASX", "Polish Notes")
        resp = await client.post("/transactions", headers=HX, data=_form(stock["id"], notes="x" * (NOTES_MAX + 1)))
        assert resp.status_code == 422
        assert f"at most {NOTES_MAX} characters" in resp.text
        assert 'id="gth-field-notes-error"' in resp.text

        resp = await client.post("/transactions", headers=HX, data=_form(stock["id"], notes="y" * NOTES_MAX))
        assert resp.status_code == 204


class TestApiNotes:
    async def test_create_and_update_reject_over_long_notes(self, client):
        headers = await register_and_login(client, "polish-api")
        stock = await create_stock(client, "PLA", "ASX", "Polish API")
        body = {"stock_id": stock["id"], "type": "Buy", "units": 1, "price": 1, "fees": 0,
                "transaction_date": "2024-08-01"}
        resp = await client.post("/api/transactions/", headers=headers, json={**body, "notes": "x" * (NOTES_MAX + 1)})
        assert resp.status_code == 422 and resp.json()["code"] == "validation_error"

        created = (await client.post("/api/transactions/", headers=headers, json={**body, "notes": "ok"})).json()
        resp = await client.put(f"/api/transactions/{created['id']}", headers=headers,
                                json={"notes": "x" * (NOTES_MAX + 1)})
        assert resp.status_code == 422


class TestImportsTruncate:
    async def test_csv_import_truncates_long_notes(self, client):
        headers = await register_and_login(client, "polish-csv")
        await create_stock(client, "PLC", "ASX", "Polish CSV")
        csv = "date,stock,type,units,price,fees,notes\n" + f"2024-08-01,ASX:PLC,Buy,10,1,0,{'n' * 600}\n"
        resp = await client.post("/api/transactions/import", headers=headers,
                                 files={"file": ("t.csv", io.BytesIO(csv.encode()), "text/csv")})
        assert resp.status_code == 200 and resp.json()["created"] == 1
        assert (await _api_items(client, headers))[0]["notes"] == "n" * NOTES_MAX

    async def test_commsec_import_truncates_long_notes(self, client):
        headers = await register_and_login(client, "polish-commsec")
        await create_stock(client, "RMD", "ASX", "ResMed Inc")
        real_parse = commsec_import.parse_commsec_email

        def long_account(*args, **kwargs):
            return dataclasses.replace(real_parse(*args, **kwargs), trading_account="9" * 600)

        with patch("pyfinbot.api.email_routes.fetch_commsec_emails", return_value=_fake_messages("bought_rmd.txt")), \
                patch("pyfinbot.api.email_routes.mark_seen"), \
                patch("pyfinbot.core.commsec_import.parse_commsec_email", side_effect=long_account):
            resp = await client.post("/api/emails/sync-commsec", headers=headers)
        assert resp.status_code == 200 and resp.json()["created"] == 1
        notes = (await _api_items(client, headers))[0]["notes"]
        assert len(notes) == NOTES_MAX and notes.startswith("Commsec email import")


class TestStockCodes:
    async def test_form_has_maxlength_without_a_counter(self, client):
        await web_login(client, "polish-stock")
        form = (await client.get("/stocks/new", headers=HX)).text
        assert form.count(f'maxlength="{CODE_MAX}"') == 2
        assert "gth-char-counter" not in form

    async def test_over_long_codes_are_field_errors(self, client):
        await web_login(client, "polish-stock-long")
        resp = await client.post("/stocks", headers=HX, data={"market": "ASX", "symbol": "S" * (CODE_MAX + 1),
                                                              "name": "Too Long"})
        assert resp.status_code == 422
        assert f"At most {CODE_MAX} characters." in resp.text
        api = await client.post("/api/stocks/", json={"market": "M" * (CODE_MAX + 1), "symbol": "OK", "name": "X"})
        assert api.status_code == 422 and api.json()["code"] == "validation_error"
