"""Unit tests for the Commsec email parser, against fixtures built from real
Commsec bought/sold confirmation emails."""
import email
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from pyfinbot.core.commsec_parser import CommsecParseError, parse_commsec_email
from pyfinbot.core.email_sync import extract_body, received_at

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "commsec_emails"


def _load_fixture(name: str) -> email.message.Message:
    text = (FIXTURES_DIR / name).read_text(encoding="utf-8")
    return email.message_from_string(text)


class TestParseBought:
    def _parse(self):
        msg = _load_fixture("bought_rmd.txt")
        return parse_commsec_email(msg["Subject"], extract_body(msg), received_at(msg))

    def test_action_and_symbol(self):
        parsed = self._parse()
        assert parsed.action == "BOUGHT"
        assert parsed.symbol == "RMD"
        assert parsed.company_name == "RESMED INC"

    def test_units_and_price(self):
        parsed = self._parse()
        assert parsed.units == Decimal("50")
        assert parsed.price_per_unit == Decimal("29.80")

    def test_derived_brokerage(self):
        parsed = self._parse()
        # total settlement 1500.00 - (50 * 29.80 = 1490.00) = 10.00
        assert parsed.brokerage == Decimal("10.00")

    def test_trade_date_from_email_header(self):
        parsed = self._parse()
        assert parsed.trade_date == date(2026, 7, 10)

    def test_settlement_date_from_body(self):
        parsed = self._parse()
        assert parsed.settlement_date == date(2026, 7, 13)


class TestParseSold:
    def _parse(self):
        msg = _load_fixture("sold_wow.txt")
        return parse_commsec_email(msg["Subject"], extract_body(msg), received_at(msg))

    def test_action_and_symbol(self):
        parsed = self._parse()
        assert parsed.action == "SOLD"
        assert parsed.symbol == "WOW"
        assert parsed.company_name == "WOOLWORTHS GROUP LIMITED"

    def test_units_and_price(self):
        parsed = self._parse()
        assert parsed.units == Decimal("579")
        assert parsed.price_per_unit == Decimal("31.581")

    def test_derived_brokerage(self):
        parsed = self._parse()
        # (579 * 31.581 = 18285.399) - 18255.31 = 30.089
        assert parsed.brokerage == Decimal("30.089")

    def test_trade_date_from_email_header(self):
        parsed = self._parse()
        assert parsed.trade_date == date(2026, 2, 5)

    def test_settlement_date_from_body(self):
        parsed = self._parse()
        assert parsed.settlement_date == date(2026, 2, 9)


class TestParseErrors:
    def test_garbage_body_raises(self):
        with pytest.raises(CommsecParseError):
            parse_commsec_email(
                "CommSec - Bought 50 units of RMD",
                "This is not a real Commsec confirmation email.",
                datetime(2026, 7, 10),
            )

    def test_garbage_subject_raises(self):
        msg = _load_fixture("bought_rmd.txt")
        with pytest.raises(CommsecParseError):
            parse_commsec_email("Your monthly statement is ready", extract_body(msg), received_at(msg))

    def test_subject_body_mismatch_raises(self):
        msg = _load_fixture("bought_rmd.txt")
        # Claim it was a Sold in the subject while the body says Bought
        with pytest.raises(CommsecParseError):
            parse_commsec_email("CommSec - Sold 50 units of RMD", extract_body(msg), received_at(msg))

    def test_subject_symbol_mismatch_raises(self):
        msg = _load_fixture("bought_rmd.txt")
        with pytest.raises(CommsecParseError):
            parse_commsec_email("CommSec - Bought 50 units of CBA", extract_body(msg), received_at(msg))

    def test_missing_settlement_clause_raises(self):
        with pytest.raises(CommsecParseError):
            parse_commsec_email(
                "CommSec - Bought 50 units of RMD",
                "You've bought 50 units in RESMED INC (RMD) at a price of $29.80 per unit "
                "(not including brokerage), on trading account ****123 MR ABC DEF GHI.",
                datetime(2026, 7, 10),
            )
