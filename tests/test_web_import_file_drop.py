"""The import page's drag-and-drop upload and the 5 MB limit (greentechhub-ui
v0.11 adoption: gth_file_drop), enforced on the server for the page and the
API alike."""
import io

import pytest

from pyfinbot.core.transaction_import import MAX_UPLOAD_BYTES, ImportFileError, read_upload

from .conftest import create_stock, hx_triggers, register_and_login, web_login

HX = {"HX-Request": "true"}
CSV_HEADER = "date,stock,type,units,price,fees,notes\n"


def _too_big() -> dict:
    # A CSV header padded past the limit: rejected before it's parsed.
    content = CSV_HEADER.encode() + b"x" * (MAX_UPLOAD_BYTES + 1 - len(CSV_HEADER))
    return {"file": ("big.csv", io.BytesIO(content), "text/csv")}


class _FakeUpload:
    def __init__(self, content: bytes):
        self._content = content
        self.asked: list[int] = []

    async def read(self, size: int = -1) -> bytes:
        self.asked.append(size)
        return self._content if size < 0 else self._content[:size]


async def test_read_upload_reads_at_most_one_byte_past_the_limit():
    exact = _FakeUpload(b"a" * 10)
    assert await read_upload(exact, limit=10) == b"a" * 10
    assert exact.asked == [11]  # never the whole file
    with pytest.raises(ImportFileError) as err:
        await read_upload(_FakeUpload(b"a" * 11), limit=10)
    assert err.value.status_code == 413
    assert MAX_UPLOAD_BYTES == 5 * 1024 * 1024


async def test_page_renders_the_drop_zone(client):
    await web_login(client, "drop-page")
    page = (await client.get("/import")).text
    assert "gth-file-drop" in page and 'data-max-size="5242880"' in page
    assert "up to 5 MB" in page and 'accept=".csv,.xls,.xlsx,.xlsm"' in page
    assert 'required="required"' in page
    assert "/js/file-drop.js" in page  # the client-side check and upload progress


async def test_oversized_upload_gets_the_error_panel(client):
    await web_login(client, "drop-big")
    resp = await client.post("/import", files=_too_big(), headers=HX)
    assert resp.status_code == 422
    assert "File is larger than 5 MB." in resp.text
    toast = hx_triggers(resp)["showToast"]
    assert toast["kind"] == "danger" and toast["message"] == "File is larger than 5 MB."


async def test_small_upload_still_imports(client):
    await web_login(client, "drop-small")
    await create_stock(client)
    csv = CSV_HEADER + "2024-08-01,ASX:BHP,Buy,10,25.50,9.95,\n"
    resp = await client.post("/import", headers=HX,
                             files={"file": ("trades.csv", io.BytesIO(csv.encode()), "text/csv")})
    assert resp.status_code == 200
    assert hx_triggers(resp)["showToast"]["message"] == "Imported 1 transaction."


async def test_api_rejects_an_oversized_file(client):
    headers = await register_and_login(client, "drop-api")
    resp = await client.post("/api/transactions/import", files=_too_big(), headers=headers)
    assert resp.status_code == 413
    assert resp.json() == {"code": "import_failed", "message": "File is larger than 5 MB.", "details": None}
