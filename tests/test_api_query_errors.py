"""The API list routes parse their query with fastapi's
PageParams.to_page_request (v0.15), which answers bad sort or filter input
with a 400 in the error envelope, so PyFinBot's own api/query.py is gone."""
import importlib.util
import json

import pytest

from .conftest import register_and_login


def test_hand_rolled_page_request_is_gone():
    assert importlib.util.find_spec("pyfinbot.api.query") is None


@pytest.mark.parametrize(("params", "code"), [
    ({"sort": "symbol,-"}, "invalid_sort"),
    ({"filters": "not json"}, "invalid_filters"),
    ({"filter": "symbol"}, "invalid_filters"),
])
async def test_stocks_bad_query_is_400_envelope(client, params, code):
    resp = await client.get("/api/stocks/", params=params)
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == code
    assert body["message"].startswith("Invalid '")


async def test_transactions_bad_query_is_400(client):
    headers = await register_and_login(client, "query-errors")
    resp = await client.get("/api/transactions/", headers=headers,
                            params={"filters": json.dumps([{"field": "units", "op": "eq"}])})
    assert resp.status_code == 400
    assert resp.json()["code"] == "invalid_filters"
