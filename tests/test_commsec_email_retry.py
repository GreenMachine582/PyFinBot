"""Commsec emails that used to fail now import: HTML-only confirmations
(message_text pads "( SKS )" and "amount , including"), stocks missing from
the ASX company list (ETFs, or before the first market sync) and, from the
Emails page, emails already marked read."""
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

from pyfinbot.core.commsec_parser import parse_commsec_email

from .conftest import register_and_login, web_login
from .test_email_accounts import FETCH, HX, MARK, _save_account
from .test_email_sync import _fake_messages

HTML_BODY = (
    "Your trade confirmation Hi Alex, You've bought 130 units in SKS TECHNOLOGIES GROUP LIMITED "
    "( SKS ) at a price of $07.55 per unit (not including brokerage), on trading account "
    "****123\xa0MR ALEX EXAMPLE. The total settlement amount , including brokerage, is $986.49 .\n"
    "    We'll debit this from your settlement account on 25 May 2026 ."
)


def test_html_spacing_parses():
    parsed = parse_commsec_email("CommSec - Bought 130 units of SKS", HTML_BODY, datetime(2026, 5, 21))
    assert (parsed.action, parsed.symbol, parsed.units) == ("BOUGHT", "SKS", Decimal("130"))
    assert parsed.company_name == "SKS TECHNOLOGIES GROUP LIMITED"
    assert parsed.price_per_unit == Decimal("7.55")
    assert parsed.total_settlement == Decimal("986.49")
    assert parsed.brokerage == Decimal("4.99")
    assert parsed.settlement_date == date(2026, 5, 25)


async def test_unknown_stock_is_created_from_the_email(gth_client):
    headers = await register_and_login(gth_client, "retry-api")
    # RMD is never registered as a Stock
    with patch("pyfinbot.api.email_routes.fetch_commsec_emails", return_value=_fake_messages("bought_rmd.txt")), \
            patch("pyfinbot.api.email_routes.mark_seen") as mark:
        data = (await gth_client.post("/api/emails/sync-commsec", headers=headers)).json()
    assert (data["created"], data["errors"]) == (1, [])
    mark.assert_called_once()
    stocks = (await gth_client.get("/api/stocks/", headers=headers)).json()["items"]
    assert [(s["market"], s["symbol"]) for s in stocks] == [("ASX", "RMD")]
    assert len((await gth_client.get("/api/transactions/", headers=headers)).json()["items"]) == 1


async def test_include_read_checkbox_reprocesses_seen_mail(gth_client):
    await web_login(gth_client, "retry-seen")
    await _save_account(gth_client, "seen@example.com")
    assert 'name="include_seen"' in (await gth_client.get("/emails")).text
    with patch(FETCH, return_value=[]) as fetch, patch(MARK):
        await gth_client.post("/emails/sync", headers=HX)
        await gth_client.post("/emails/sync", headers=HX, data={"include_seen": "1"})
    assert [c.kwargs["only_unseen"] for c in fetch.call_args_list] == [True, False]
