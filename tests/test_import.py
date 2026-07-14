"""Integration tests for /api/transactions/import endpoint."""
import io



USER_HEADERS = {"X-User-ID": "importer-user"}

CSV_HEADER = "date,stock,type,units,price,fees,notes\n"


async def _create_stock(client, symbol="BHP", market="ASX", name="BHP Group"):
    resp = await client.post("/api/stocks/", json={"symbol": symbol, "market": market, "name": name})
    assert resp.status_code == 201
    return resp.json()


def _csv_file(content: str) -> dict:
    return {"file": ("transactions.csv", io.BytesIO(content.encode()), "text/csv")}


class TestImportCSV:
    async def test_single_valid_row(self, client):
        await _create_stock(client)
        csv = CSV_HEADER + "2024-08-01,ASX:BHP,Buy,10,25.50,9.95,Test import\n"
        resp = await client.post("/api/transactions/import",
                                 files=_csv_file(csv), headers=USER_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 1
        assert data["skipped"] == 0
        assert data["errors"] == []

    async def test_multiple_rows(self, client):
        await _create_stock(client, "BHP")
        await _create_stock(client, "CBA", name="Commonwealth Bank")
        csv = (CSV_HEADER
               + "2024-08-01,ASX:BHP,Buy,10,25.50,9.95,\n"
               + "2024-08-02,ASX:CBA,Sell,5,100.00,9.95,\n")
        resp = await client.post("/api/transactions/import",
                                 files=_csv_file(csv), headers=USER_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 2
        assert data["skipped"] == 0

    async def test_slash_date_format(self, client):
        await _create_stock(client)
        csv = CSV_HEADER + "01/08/2024,ASX:BHP,Buy,10,25.50,,\n"
        resp = await client.post("/api/transactions/import",
                                 files=_csv_file(csv), headers=USER_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["created"] == 1

    async def test_separate_market_column(self, client):
        await _create_stock(client)
        csv = "date,stock,market,type,units,price\n2024-08-01,BHP,ASX,Buy,10,25.50\n"
        resp = await client.post("/api/transactions/import",
                                 files=_csv_file(csv), headers=USER_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["created"] == 1

    async def test_unknown_stock_skips_row(self, client):
        csv = CSV_HEADER + "2024-08-01,ASX:UNKNOWN,Buy,10,25.50,,\n"
        resp = await client.post("/api/transactions/import",
                                 files=_csv_file(csv), headers=USER_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 0
        assert data["skipped"] == 1
        assert len(data["errors"]) == 1

    async def test_invalid_type_skips_row(self, client):
        await _create_stock(client)
        csv = CSV_HEADER + "2024-08-01,ASX:BHP,Hold,10,25.50,,\n"
        resp = await client.post("/api/transactions/import",
                                 files=_csv_file(csv), headers=USER_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["skipped"] == 1

    async def test_mixed_valid_and_invalid_rows(self, client):
        await _create_stock(client)
        csv = (CSV_HEADER
               + "2024-08-01,ASX:BHP,Buy,10,25.50,,\n"
               + "2024-08-02,ASX:NOPE,Buy,1,1.00,,\n")
        resp = await client.post("/api/transactions/import",
                                 files=_csv_file(csv), headers=USER_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 1
        assert data["skipped"] == 1

    async def test_reupload_same_file_skips_duplicates(self, client):
        await _create_stock(client)
        csv = CSV_HEADER + "2024-08-01,ASX:BHP,Buy,10,25.50,9.95,Test import\n"
        first = await client.post("/api/transactions/import",
                                  files=_csv_file(csv), headers=USER_HEADERS)
        assert first.status_code == 200
        assert first.json()["created"] == 1

        second = await client.post("/api/transactions/import",
                                   files=_csv_file(csv), headers=USER_HEADERS)
        assert second.status_code == 200
        data = second.json()
        assert data["created"] == 0
        assert data["skipped"] == 1
        assert "duplicate" in data["errors"][0].lower()

    async def test_duplicate_rows_within_same_file_skips_second(self, client):
        await _create_stock(client)
        csv = (CSV_HEADER
               + "2024-08-01,ASX:BHP,Buy,10,25.50,9.95,\n"
               + "2024-08-01,ASX:BHP,Buy,10,25.50,9.95,\n")
        resp = await client.post("/api/transactions/import",
                                 files=_csv_file(csv), headers=USER_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 1
        assert data["skipped"] == 1

    async def test_different_fees_not_treated_as_duplicate(self, client):
        await _create_stock(client)
        csv = (CSV_HEADER
               + "2024-08-01,ASX:BHP,Buy,10,25.50,9.95,\n"
               + "2024-08-01,ASX:BHP,Buy,10,25.50,4.95,\n")
        resp = await client.post("/api/transactions/import",
                                 files=_csv_file(csv), headers=USER_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 2
        assert data["skipped"] == 0

    async def test_missing_required_column_returns_422(self, client):
        csv = "date,stock,units,price\n2024-08-01,ASX:BHP,10,25.50\n"  # missing type
        resp = await client.post("/api/transactions/import",
                                 files=_csv_file(csv), headers=USER_HEADERS)
        assert resp.status_code == 422

    async def test_no_user_id_header_returns_400(self, client):
        csv = CSV_HEADER + "2024-08-01,ASX:BHP,Buy,10,25.50,,\n"
        resp = await client.post("/api/transactions/import", files=_csv_file(csv))
        assert resp.status_code == 400

    async def test_empty_file_returns_400(self, client):
        resp = await client.post("/api/transactions/import",
                                 files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
                                 headers=USER_HEADERS)
        assert resp.status_code == 400
