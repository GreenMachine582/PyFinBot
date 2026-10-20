"""The development demo seed (greentechhub v0.12 adoption, item 2)."""
from collections import defaultdict
from decimal import Decimal

import pytest
from greentechhub_core.security import verify_password
from sqlmodel import select

from pyfinbot.dev import seed as seed_module
from pyfinbot.dev.seed import (
    DEMO_STOCKS,
    DEMO_USERS,
    TRANSACTION_COUNTS,
    DemoSeedRefused,
    seed_demo,
)
from pyfinbot.models.dividend_models import Dividend
from pyfinbot.models.stock_models import Stock
from pyfinbot.models.transaction_models import Transaction, TypeEnum

from .conftest import account_row, insert_account, post_login

HX = {"HX-Request": "true"}


async def _all(session, model, *where):
    return list((await session.exec(select(model).where(*where))).all())


async def _demo_transactions(session, username):
    user_id = (await account_row(session, username)).id
    stmt = (select(Transaction).where(Transaction.user_id == user_id)
            .order_by(Transaction.transaction_date, Transaction.id))
    return list((await session.exec(stmt)).all())


async def test_first_run_creates_the_demo_data(gth_session):
    summary = await seed_demo(gth_session, environment="development")
    assert summary.users_created == 2 and summary.stocks_created == len(DEMO_STOCKS) == 8

    for username, password in DEMO_USERS.items():
        user = await account_row(gth_session, username)
        assert user is not None and user.active and verify_password(password, user.password_hash)
        assert user.email_verified and user.display_name

    stocks = await _all(gth_session, Stock, Stock.market == "ASX")
    assert len(stocks) == 8
    archived = {s.symbol for s in stocks if not s.is_active}
    assert archived == {"TLS", "FMG"} and all(s.archived_at for s in stocks if not s.is_active)

    for user_id, count in TRANSACTION_COUNTS.items():
        rows = await _demo_transactions(gth_session, user_id)
        assert count <= len(rows) <= count + 2  # plus a sell-out per archived stock held
        assert {r.type for r in rows} == {TypeEnum.BUY, TypeEnum.SELL}
        assert len({r.fy for r in rows}) == 3  # FY2023-24 .. FY2025-26
        assert sum(1 for r in rows if r.notes) >= 2
    assert summary.transactions_created >= sum(TRANSACTION_COUNTS.values())

    dividends = await _all(gth_session, Dividend, Dividend.source == "demo")
    assert len(dividends) == summary.dividends_created == 6 * 6  # 6 active stocks, 6 ex-dates


async def test_holdings_never_go_negative_and_archived_stocks_end_flat(gth_session):
    await seed_demo(gth_session, environment="development")
    stocks = {s.id: s for s in await _all(gth_session, Stock)}
    for user_id in DEMO_USERS:
        held: dict[int, Decimal] = defaultdict(Decimal)
        for row in await _demo_transactions(gth_session, user_id):
            held[row.stock_id] += row.units if row.type is TypeEnum.BUY else -row.units
            assert held[row.stock_id] >= 0, (user_id, row)
            stock = stocks[row.stock_id]
            if stock.archived_at:
                assert row.transaction_date < stock.archived_at.date()
        for stock_id, units in held.items():
            if not stocks[stock_id].is_active:
                assert units == 0


async def test_second_run_adds_nothing(gth_session):
    await seed_demo(gth_session, environment="development")
    before = (len(await _all(gth_session, Transaction)), len(await _all(gth_session, Dividend)))
    again = await seed_demo(gth_session, environment="development")
    assert not again.created_anything
    assert (len(await _all(gth_session, Transaction)), len(await _all(gth_session, Dividend))) == before


async def test_reset_removes_only_the_seeds_rows(gth_session):
    await seed_demo(gth_session, environment="development")
    bhp = await Stock.search(gth_session, market="ASX", symbol="BHP")
    real_user = await insert_account(gth_session, "real-user")
    gth_session.add(Transaction(user_id=real_user, stock_id=bhp.id, type=TypeEnum.BUY,
                            units=Decimal(5), price=Decimal(40)))
    await gth_session.commit()

    summary = await seed_demo(gth_session, reset=True, environment="development")
    assert summary.reset["users"] == 2 and summary.reset["dividends"] == 36
    assert summary.reset["stocks"] == 7  # BHP stays: real-user still trades it
    assert summary.users_created == 2 and summary.stocks_created == 7
    assert len(await _all(gth_session, Transaction, Transaction.user_id == real_user)) == 1
    assert (await Stock.search(gth_session, market="ASX", symbol="BHP")).id == bhp.id


@pytest.mark.parametrize("environment", ["production", "staging", ""])
async def test_refuses_outside_development(gth_session, environment):
    with pytest.raises(DemoSeedRefused):
        await seed_demo(gth_session, environment=environment)
    assert await account_row(gth_session, "demo-admin") is None


def test_cli_refuses_in_production(monkeypatch, capsys):
    monkeypatch.setattr(seed_module.settings, "environment", "production")
    assert seed_module.main(["--reset"]) == 2
    assert "development only" in capsys.readouterr().err


async def test_seeded_transactions_page_for_demo_user(gth_client, gth_session):
    await seed_demo(gth_session, environment="development")
    login = await post_login(gth_client, "demo-user", "demo-user-pass",
                              follow_redirects=False)
    assert login.status_code == 303
    # Secure cookie over the tests' http:// base URL: re-set it, as web_login does.
    gth_client.cookies.set("gth_session", login.cookies["gth_session"])
    resp = await gth_client.get("/transactions", headers=HX)
    assert resp.status_code == 200
    total = len(await _demo_transactions(gth_session, "demo-user"))
    # More than one page: the table's "Load more" shows, with the total.
    assert f"({total} total)" in resp.text and 'data-gth-table-mode="load_more"' in resp.text
    assert "Load more" in resp.text
