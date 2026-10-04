"""Bulk delete on the Transactions table: gth_data_table's bulk bar posts
the checked rows as repeated `ids` (after a confirm) to
POST /transactions/bulk-delete, which deletes only the signed-in user's."""
from .conftest import create_stock, hx_triggers, web_login

HX = {"HX-Request": "true"}


async def _add(client, stock_id, day: str) -> None:
    resp = await client.post("/transactions", headers=HX, data={
        "stock_id": str(stock_id), "transaction_date": day, "type": "Buy",
        "units": "1", "price": "1", "fees": "0", "notes": ""})
    assert resp.status_code == 204, resp.text


async def _my_ids(client) -> list[int]:
    """The signed-in user's transaction ids, read from the table's select cells."""
    page = (await client.get("/transactions", headers=HX, params={"size": 50})).text
    marker = 'data-gth-select value="'
    return sorted(int(chunk.split('"', 1)[0]) for chunk in page.split(marker)[1:])


async def _sign_in_again(client, user_id: str) -> None:
    """Switch back to an existing user (web_login would create them again)."""
    resp = await client.post("/login", data={"user_id": user_id, "password": "hunter2!"}, follow_redirects=False)
    assert resp.status_code == 303, resp.text
    client.cookies.set("gth_session", resp.cookies["gth_session"])


async def _delete(client, ids):
    return await client.post("/transactions/bulk-delete", headers=HX, data={"ids": [str(i) for i in ids]})


async def test_table_has_the_delete_bulk_action_and_select_cells(client):
    await web_login(client, "tbulk-view")
    stock = await create_stock(client, "TBV", "ASX", "Bulk View")
    await _add(client, stock["id"], "2024-08-01")
    page = (await client.get("/transactions", headers=HX)).text
    assert 'hx-post="/transactions/bulk-delete"' in page
    assert 'hx-confirm="Delete the selected transactions? This can&#39;t be undone."' in page
    assert "btn btn-sm btn-outline-danger" in page
    assert page.count("data-gth-select ") == 1
    assert 'aria-label="Select Buy TBV on 1 Aug 2024"' in page


async def test_deletes_the_selected_rows_only(client):
    await web_login(client, "tbulk-user")
    stock = await create_stock(client, "TBU", "ASX", "Bulk User")
    for day in ("2024-08-01", "2024-08-02", "2024-08-03"):
        await _add(client, stock["id"], day)
    first, second, third = await _my_ids(client)

    resp = await _delete(client, [first, third])
    assert resp.status_code == 204
    triggers = hx_triggers(resp)
    assert triggers["showToast"]["message"] == "Deleted 2 transactions"
    assert triggers["showToast"]["title"] == "Transactions deleted"
    assert "transactionsChanged" in triggers
    assert await _my_ids(client) == [second]

    assert hx_triggers(await _delete(client, [second]))["showToast"]["message"] == "Deleted 1 transaction"


async def test_another_users_ids_are_ignored(client):
    stock = await create_stock(client, "TBO", "ASX", "Bulk Owner")
    await web_login(client, "tbulk-a")
    await _add(client, stock["id"], "2024-08-01")
    a_ids = await _my_ids(client)

    await web_login(client, "tbulk-b")
    await _add(client, stock["id"], "2024-09-01")
    b_ids = await _my_ids(client)

    resp = await _delete(client, a_ids)
    assert hx_triggers(resp)["showToast"]["kind"] == "info"
    resp = await _delete(client, a_ids + b_ids)
    assert hx_triggers(resp)["showToast"]["message"] == "Deleted 1 transaction"
    assert await _my_ids(client) == []

    await _sign_in_again(client, "tbulk-a")
    assert await _my_ids(client) == a_ids  # untouched


async def test_junk_or_empty_selection_is_an_info_toast(client):
    await web_login(client, "tbulk-empty")
    for data in ({"ids": ["nope", "999999"]}, {}):
        resp = await client.post("/transactions/bulk-delete", headers=HX, data=data)
        toast = hx_triggers(resp)
        assert toast["showToast"]["kind"] == "info"
        assert toast["showToast"]["message"] == "No transactions to delete."
        assert "transactionsChanged" in toast


async def test_needs_login(client):
    resp = await client.post("/transactions/bulk-delete", headers=HX, data={"ids": ["1"]}, follow_redirects=False)
    assert resp.status_code == 401
    assert resp.headers["HX-Redirect"] == "/login"
