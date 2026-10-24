"""The API's row lookups on greentechhub-fastapi's get_owned_or_404: someone
else's transaction is the same 404 as a missing one (as on the web routes),
and a deactivated user's token is refused."""

from .conftest import create_stock, register_and_login, user_id

TXN = {"transaction_date": "2024-08-01", "type": "Buy", "units": "10", "price": "20", "fees": "0"}


async def test_deleting_someone_elses_transaction_is_a_404(gth_client):
    alice = await register_and_login(gth_client, "owned-alice")
    bob = await register_and_login(gth_client, "owned-bob")
    stock = await create_stock(gth_client, "OWN", "ASX", "Owned Co")
    created = await gth_client.post("/api/transactions/", headers=alice, json={**TXN, "stock_id": stock["id"]})
    assert created.status_code == 201, created.text
    txn_id = created.json()["id"]

    theirs = await gth_client.delete(f"/api/transactions/{txn_id}", headers=bob)
    missing = await gth_client.delete("/api/transactions/999999", headers=bob)
    assert theirs.status_code == missing.status_code == 404
    assert theirs.json()["code"] == missing.json()["code"] == "not_found"
    assert (await gth_client.delete(f"/api/transactions/{txn_id}", headers=alice)).status_code == 204


async def test_a_deactivated_users_token_is_refused(gth_client):
    carol = await register_and_login(gth_client, "owned-carol")
    me = await user_id("owned-carol")
    assert (await gth_client.delete(f"/api/users/{me}", headers=carol)).status_code == 204
    gone = await gth_client.get(f"/api/users/{me}", headers=carol)  # unexpired, but the account is off
    assert gone.status_code == 401 and gone.json()["code"] == "unauthorized"
