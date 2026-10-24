"""Page filters read through greentechhub-fastapi v0.18's lenient query
parsers (optional_date / optional_int / optional_choice): a blank or
unreadable value gives the default rather than a 422, so a stale or
hand-edited URL still renders."""
from .conftest import create_stock, web_login
from .test_web_reports import _seed
from .test_web_transactions import _add

HX = {"HX-Request": "true"}


async def test_bad_report_filters_fall_back_to_the_defaults(gth_client, gth_session):
    await web_login(gth_client, "lenient-reports")
    await _seed(gth_client, gth_session)

    # Today's holdings at average cost: 150 BHP left after the sell.
    resp = await gth_client.get("/reports/holdings", params={"as_of": "nope", "method": "nope"})
    assert resp.status_code == 200 and "150" in resp.text

    # No readable FY: the user's latest (FY2024, the sell's), gain 740.
    resp = await gth_client.get("/reports/gains", params={"fy": "abc", "method": " "})
    assert resp.status_code == 200 and "740.00" in resp.text

    resp = await gth_client.get("/reports/dividends", params={"fy": "all"})
    assert resp.status_code == 200 and "Received, all time" in resp.text


async def test_good_report_filters_still_apply(gth_client, gth_session):
    await web_login(gth_client, "lenient-reports-ok")
    await _seed(gth_client, gth_session)
    resp = await gth_client.get("/reports/gains.csv", params={"fy": " 2024 ", "method": "fifo"})
    assert 'filename="pyfinbot-gains-fy2024-fifo.csv"' in resp.headers["content-disposition"]
    resp = await gth_client.get("/reports/holdings.csv", params={"as_of": "2024-12-31", "method": "bogus"})
    assert 'filename="pyfinbot-holdings-2024-12-31.csv"' in resp.headers["content-disposition"]


async def test_bad_transaction_filters_are_ignored(gth_client):
    await web_login(gth_client, "lenient-txn")
    bhp = await create_stock(gth_client, "BHP")
    await _add(gth_client, bhp["id"], notes="bhp-buy", transaction_date="2023-08-01")
    await _add(gth_client, bhp["id"], notes="bhp-sell", type="Sell", units="1", transaction_date="2024-08-01")

    resp = await gth_client.get("/transactions", headers=HX,
                                params={"type": "Nope", "fy": "x", "date_from": "nope", "date_to": ""})
    assert resp.status_code == 200 and "bhp-buy" in resp.text and "bhp-sell" in resp.text

    resp = await gth_client.get("/transactions", headers=HX, params={"type": "Sell", "fy": "2024"})
    assert "bhp-sell" in resp.text and "bhp-buy" not in resp.text
