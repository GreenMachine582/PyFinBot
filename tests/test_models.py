"""Unit tests for Transaction model derived fields (no DB required)."""
from datetime import date
from decimal import Decimal

import pytest

from pyfinbot.models.transaction_models import Transaction, TypeEnum
from pyfinbot.schemas.transaction_schemas import TransactionBase


class TestTransactionDerivedFields:
    def test_buy_total_value(self):
        t = Transaction(user_id="u1", stock_id=1, type=TypeEnum.BUY,
                        units=10, price=5, fees=0, transaction_date=date(2024, 8, 1))
        assert t.total_value == Decimal("50.000000")

    def test_buy_cost_is_negative(self):
        t = Transaction(user_id="u1", stock_id=1, type=TypeEnum.BUY,
                        units=10, price=5, fees=Decimal("0.5"),
                        transaction_date=date(2024, 8, 1))
        assert t.cost == Decimal("-50.500000")

    def test_sell_total_value(self):
        t = Transaction(user_id="u1", stock_id=1, type=TypeEnum.SELL,
                        units=10, price=5, fees=0, transaction_date=date(2024, 8, 1))
        assert t.total_value == Decimal("50.000000")

    def test_sell_cost_is_positive_minus_fees(self):
        t = Transaction(user_id="u1", stock_id=1, type=TypeEnum.SELL,
                        units=10, price=5, fees=Decimal("0.5"),
                        transaction_date=date(2024, 8, 1))
        assert t.cost == Decimal("49.500000")

    def test_fy_july_starts_new_year(self):
        t = Transaction(user_id="u1", stock_id=1, type=TypeEnum.BUY,
                        units=1, price=1, transaction_date=date(2024, 7, 1))
        assert t.fy == 2024

    def test_fy_june_ends_previous_year(self):
        t = Transaction(user_id="u1", stock_id=1, type=TypeEnum.BUY,
                        units=1, price=1, transaction_date=date(2024, 6, 30))
        assert t.fy == 2023

    def test_fy_january_is_previous_year(self):
        t = Transaction(user_id="u1", stock_id=1, type=TypeEnum.BUY,
                        units=1, price=1, transaction_date=date(2025, 1, 15))
        assert t.fy == 2024


class TestTransactionDateParsing:
    def test_iso_date_string(self):
        t = TransactionBase(stock_id=1, type=TypeEnum.BUY, units=1, price=1,
                            transaction_date="2024-08-15")
        assert t.transaction_date == date(2024, 8, 15)

    def test_slash_date_string(self):
        t = TransactionBase(stock_id=1, type=TypeEnum.BUY, units=1, price=1,
                            transaction_date="15/08/2024")
        assert t.transaction_date == date(2024, 8, 15)

    def test_invalid_date_raises(self):
        with pytest.raises(Exception):
            TransactionBase(stock_id=1, type=TypeEnum.BUY, units=1, price=1,
                            transaction_date="not-a-date")

    def test_none_date_defaults_to_today(self):
        # model_post_init (on Transaction, not TransactionBase) fills None → today
        t = Transaction(user_id="u1", stock_id=1, type=TypeEnum.BUY, units=1, price=1,
                        transaction_date=None)
        from datetime import date as _date
        assert t.transaction_date == _date.today()


class TestTypeEnumCaseInsensitive:
    def test_lowercase_buy(self):
        assert TypeEnum("buy") == TypeEnum.BUY

    def test_mixed_case_sell(self):
        assert TypeEnum("Sell") == TypeEnum.SELL

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            TypeEnum("hold")
