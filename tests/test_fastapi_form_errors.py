"""The transaction form's validation errors come from greentechhub-fastapi's
forms.field_errors (v0.15) instead of a hand-rolled _field_errors: pydantic's
message, filed under its field, re-rendered with the form at 422."""
from pyfinbot.web.routes import transactions

from .conftest import create_stock, web_login
from .test_web_transactions_export import _form


def test_hand_rolled_field_errors_is_gone():
    assert not hasattr(transactions, "_field_errors")


async def test_unparseable_number_shows_pydantics_message_on_its_field(client):
    stock = await create_stock(client)
    await web_login(client, "form-errors")
    resp = await client.post("/transactions", data=_form(stock["id"], price="cheap"))
    assert resp.status_code == 422
    error = resp.text.split('id="gth-field-price-error"', 1)[1].split("</div>", 1)[0]
    assert "Input should be a valid number" in error
