"""ImportFileError and EmailSyncError are core ApplicationErrors (todo › Lean
now): the API's error handlers answer them directly, with no remapping in
the routes."""
from unittest.mock import AsyncMock, patch

from greentechhub_core.types import ApplicationError
from httpx import AsyncClient

from pyfinbot.core.commsec_import import EmailSyncError
from pyfinbot.core.transaction_import import ImportFileError

from .conftest import register_and_login


def test_both_are_application_errors_with_their_code_and_status():
    imp = ImportFileError(413, "File is larger than 5 MB.")
    sync = EmailSyncError(503, "Set up your email account first.")
    assert isinstance(imp, ApplicationError) and isinstance(sync, ApplicationError)
    assert (imp.code, imp.status_code, imp.message) == ("import_failed", 413, "File is larger than 5 MB.")
    assert (sync.code, sync.status_code, str(sync)) == ("email_sync_failed", 503,
                                                        "Set up your email account first.")


async def test_the_api_answers_an_email_sync_error_from_its_status(client: AsyncClient):
    headers = await register_and_login(client, "errors-a")
    with patch("pyfinbot.api.email_routes._sync_commsec_emails",
               new=AsyncMock(side_effect=EmailSyncError(502, "IMAP fetch failed: timed out"))), \
         patch("pyfinbot.api.email_routes.load_email_account", new=AsyncMock()):
        resp = await client.post("/api/emails/sync-commsec", headers=headers)
    assert resp.status_code == 502
    assert resp.json() == {"code": "email_sync_failed", "message": "IMAP fetch failed: timed out",
                           "details": None}


async def test_the_api_answers_an_empty_import_as_a_400(client: AsyncClient):
    headers = await register_and_login(client, "errors-b")
    resp = await client.post("/api/transactions/import", headers=headers,
                             files={"file": ("empty.csv", b"", "text/csv")})
    assert resp.status_code == 400
    assert resp.json()["code"] == "import_failed"
    assert resp.json()["message"] == "Uploaded file is empty"
