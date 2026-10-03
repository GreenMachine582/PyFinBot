"""/api errors come from greentechhub: core's BadRequestError / the
ApplicationError status_code hint and fastapi's register_api_error_handlers
replace PyFinBot's own StatusError (core/errors.py) and web/api_errors.py,
with the same statuses and {code, message, details} bodies as before."""
import importlib.util
import io
from unittest.mock import patch

import pytest

from pyfinbot.core.transaction_import import MAX_UPLOAD_BYTES

from .conftest import create_stock, register_and_login

HTML = {"Accept": "text/html"}


@pytest.mark.parametrize("module", ["pyfinbot.core.errors", "pyfinbot.web.api_errors"])
def test_hand_rolled_error_modules_are_gone(module):
    assert importlib.util.find_spec(module) is None


async def test_a_fixed_400_is_core_bad_request_with_its_own_code(client):
    await create_stock(client, "ERR", "ASX", "Error Test")
    resp = await client.post("/api/stocks/", json={"symbol": "ERR", "market": "ASX", "name": "Again"})
    assert resp.status_code == 400
    assert resp.json() == {"code": "stock_exists", "message": "Stock already registered", "details": None}


async def test_a_runtime_status_comes_from_the_status_code_hint(client):
    headers = await register_and_login(client, "err-import")
    big = io.BytesIO(b"x" * (MAX_UPLOAD_BYTES + 1))
    resp = await client.post("/api/transactions/import", headers=headers,
                             files={"file": ("big.csv", big, "text/csv")})
    assert resp.status_code == 413
    body = resp.json()
    assert body["code"] == "import_failed" and "5 MB" in body["message"]


async def test_a_502_sync_failure_keeps_its_status(client):
    headers = await register_and_login(client, "err-email")
    with patch("pyfinbot.api.email_routes.fetch_commsec_emails", side_effect=RuntimeError("connection refused")):
        resp = await client.post("/api/emails/sync-commsec", headers=headers)
    assert resp.status_code == 502
    assert resp.json() == {"code": "email_sync_failed", "message": "IMAP fetch failed: connection refused",
                           "details": None}


async def test_api_401_has_the_bearer_challenge_and_the_envelope(client):
    resp = await client.get("/api/transactions/")
    assert resp.status_code == 401
    assert resp.headers["WWW-Authenticate"] == "Bearer"
    assert resp.json()["code"] == "unauthorized"


async def test_unknown_api_route_is_the_not_found_envelope(client):
    resp = await client.get("/api/nope")
    assert resp.status_code == 404
    assert resp.json() == {"code": "not_found", "message": "Not Found", "details": None}


async def test_pages_keep_fastapis_defaults(client):
    resp = await client.get("/nope", headers=HTML)
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Not Found"}  # not the envelope
    resp = await client.get("/transactions", headers=HTML, follow_redirects=False)
    assert resp.status_code == 303 and resp.headers["location"] == "/login"
