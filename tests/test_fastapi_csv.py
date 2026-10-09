"""CSV downloads through greentechhub-fastapi's downloads module (v0.15):
csv_download for the transactions and report exports, csv_value for the
transactions' Decimal cells, and its BOM for the CLI's CSV files. PyFinBot's own
web/csv_response.py is gone."""
import importlib.util

from httpx import AsyncClient

from .conftest import create_stock, web_login
from .test_cli import _cli
from .test_web_transactions_export import _add, _rows


def test_hand_rolled_csv_response_is_gone():
    assert importlib.util.find_spec("pyfinbot.web.csv_response") is None


async def test_transaction_decimals_are_plain_and_trimmed(client: AsyncClient):
    bhp = await create_stock(client)
    await web_login(client, "fastapi-csv")
    await _add(client, bhp["id"], units="1000", price="12.50", fees="0")
    row = _rows(await client.get("/transactions.csv"))[1]
    units, price, fees = row[4:7]
    assert (units, price, fees) == ("1000", "12.5", "0")  # not "1E+3" or "12.50"


async def test_cli_csv_file_starts_with_the_bom(client: AsyncClient, tmp_path):
    await web_login(client, "fastapi-csv-cli")
    out = tmp_path / "holdings.csv"
    code, _, _ = await _cli("holdings", "--user", "fastapi-csv-cli", "-o", str(out))
    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert text.startswith(chr(0xFEFF)) and text.count(chr(0xFEFF)) == 1
