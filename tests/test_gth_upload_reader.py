"""Import uploads read through greentechhub-fastapi v0.18's
uploads.read_upload: over MAX_UPLOAD_BYTES is its 413 UploadTooLargeError,
the shared payload_too_large envelope on the API and the usual error panel
on the page; a file that fits still reaches the importer."""
import io

from pyfinbot.core.transaction_import import MAX_UPLOAD_BYTES

from .conftest import hx_triggers, register_and_login, web_login

HX = {"HX-Request": "true"}


def _file(size: int) -> dict:
    return {"file": ("big.csv", io.BytesIO(b"x" * size), "text/csv")}


async def test_the_api_answers_an_oversized_file_with_payload_too_large(gth_client):
    headers = await register_and_login(gth_client, "reader-api")
    resp = await gth_client.post("/api/transactions/import", headers=headers, files=_file(MAX_UPLOAD_BYTES + 1))
    assert resp.status_code == 413
    assert resp.json() == {"code": "payload_too_large", "message": "File is larger than 5 MB.", "details": None}


async def test_a_file_at_the_limit_reaches_the_importer(gth_client):
    headers = await register_and_login(gth_client, "reader-limit")
    resp = await gth_client.post("/api/transactions/import", headers=headers, files=_file(MAX_UPLOAD_BYTES))
    # Read whole, then refused by the importer (no columns), not by the size cap.
    assert resp.status_code != 413 and resp.json()["code"] == "import_failed"


async def test_the_page_shows_an_oversized_file_as_a_form_error(gth_client):
    await web_login(gth_client, "reader-page")
    resp = await gth_client.post("/import", headers=HX, files=_file(MAX_UPLOAD_BYTES + 1))
    assert resp.status_code == 422 and "File is larger than 5 MB." in resp.text
    toast = hx_triggers(resp)["showToast"]
    assert (toast["kind"], toast["title"]) == ("danger", "Import failed")
