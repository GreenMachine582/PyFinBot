"""The transactions table's CSV export and column view options, and the row
actions column on the transactions and stocks tables (greentechhub-ui v0.14)."""
import csv
import io

from httpx import AsyncClient

from .conftest import create_stock, web_login

HX = {"HX-Request": "true"}
HEADER = ["Date", "Market", "Symbol", "Type", "Units", "Price", "Fees", "Total", "Cost", "FY", "Notes"]


def _form(stock_id, **overrides) -> dict:
    return {"stock_id": str(stock_id), "transaction_date": "2024-08-01", "type": "Buy", "units": "10",
            "price": "25.5", "fees": "9.95", "notes": "", **overrides}


async def _add(client: AsyncClient, stock_id, **overrides) -> None:
    resp = await client.post("/transactions", data=_form(stock_id, **overrides))
    assert resp.status_code == 204, resp.text


def _rows(resp) -> list[list[str]]:
    return list(csv.reader(io.StringIO(resp.text)))


async def test_export_needs_a_signed_in_user(client: AsyncClient):
    resp = await client.get("/transactions.csv", follow_redirects=False)
    assert resp.status_code == 303 and resp.headers["location"] == "/login"


async def test_export_is_the_users_rows_as_a_csv_download(client: AsyncClient):
    bhp = await create_stock(client)
    await web_login(client, "export-other")
    await _add(client, bhp["id"], notes="someone else's")
    await web_login(client, "export-a")
    await _add(client, bhp["id"], notes="first, buy")

    resp = await client.get("/transactions.csv")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert resp.headers["content-disposition"] == 'attachment; filename="pyfinbot-transactions.csv"'
    rows = _rows(resp)
    assert rows[0] == HEADER
    assert len(rows) == 2  # only this user's transaction
    date, market, symbol, type_, units, price, fees, total, cost, fy, notes = rows[1]
    assert (date, market, symbol, type_) == ("2024-08-01", "ASX", "BHP", "Buy")
    assert (units, price, fees) == ("10", "25.5", "9.95")  # plain decimals, trailing zeros trimmed
    assert fy == "2024–25" and notes == "first, buy"  # the table's FY label; csv quotes the comma


async def test_export_takes_the_filters_and_sort_but_not_paging(client: AsyncClient):
    bhp = await create_stock(client)
    cba = await create_stock(client, "CBA", name="Commonwealth Bank")
    await web_login(client, "export-b")
    for day in range(1, 11):  # 10 BHP buys in Aug 2024
        await _add(client, bhp["id"], transaction_date=f"2024-08-{day:02d}")
    await _add(client, bhp["id"], transaction_date="2024-09-01", type="Sell", units="2")
    await _add(client, cba["id"], transaction_date="2023-05-01")

    every = _rows(await client.get("/transactions.csv", params={"size": "10", "page": "2"}))
    assert len(every) - 1 == 12  # page and size are ignored: every matching row

    buys = _rows(await client.get("/transactions.csv", params={"type": "Buy", "stock": "bhp"}))
    assert len(buys) - 1 == 10 and {r[2] for r in buys[1:]} == {"BHP"}

    fy = _rows(await client.get("/transactions.csv", params={"fy": "2022"}))
    assert [r[2] for r in fy[1:]] == ["CBA"]

    in_range = _rows(await client.get("/transactions.csv", params={"date_from": "2024-08-05",
                                                                   "date_to": "2024-08-07"}))
    assert [r[0] for r in in_range[1:]] == ["2024-08-07", "2024-08-06", "2024-08-05"]  # newest first

    oldest_first = _rows(await client.get("/transactions.csv",
                                          params={"sort": "transaction_date", "dir": "asc"}))
    assert oldest_first[1][0] == "2023-05-01" and oldest_first[-1][0] == "2024-09-01"


async def test_table_has_export_link_view_menu_and_row_actions(client: AsyncClient):
    bhp = await create_stock(client)
    await web_login(client, "export-c")
    await _add(client, bhp["id"])

    html = (await client.get("/transactions", headers=HX, params={"type": "Buy", "page": "1"})).text
    # Export: the current filters, never page or size.
    assert 'href="/transactions.csv?type=Buy' in html and "transactions.csv?page" not in html
    # View menu: Date and Stock pinned, Notes hidden until shown, no blank toggle.
    assert 'data-gth-col="transaction_date" data-gth-pinned' in html
    assert 'data-gth-col="Stock" data-gth-pinned' in html
    assert 'data-gth-col="Notes" data-default-hidden' in html
    assert 'data-gth-col-toggle=""' not in html and 'data-gth-col=""' not in html
    # Row actions: their own column, edit/delete opening the modal host.
    assert '<span class="visually-hidden">Actions</span>' in html
    assert '<td class="gth-table-actions">' in html
    assert 'aria-label="Edit Buy BHP"' in html and 'aria-label="Delete Buy BHP"' in html
    assert 'hx-get="/transactions/' in html and 'hx-target="#gth-modal-host"' in html


async def test_stock_table_has_the_row_actions_column(client: AsyncClient):
    await create_stock(client)
    await web_login(client, "export-d")
    html = (await client.get("/stocks", headers=HX)).text
    assert '<span class="visually-hidden">Actions</span>' in html
    assert 'aria-label="Edit BHP"' in html and 'aria-label="Delete BHP"' in html
    assert '<th scope="col"></th>' not in html  # no hand-built blank header
