"""Demo data for local development: two users, eight ASX stocks (two
archived), ~150 transactions over three Australian financial years, and
dividends — enough to page, filter and report on.

    python scripts/seed_demo.py           # idempotent: a second run adds nothing
    python scripts/seed_demo.py --reset   # wipe the demo rows, then seed again

Refuses to run unless ENVIRONMENT == "development". The data is generated
from a fixed random seed, so every developer gets the same rows.

Stocks and dividends are global (not per user), so reset only removes what
the seed owns: the demo users and their transactions, dividends with
source="demo", and demo stocks nothing else refers to any more.
"""

import argparse
import asyncio
import random
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Sequence, cast

from sqlalchemy import CursorResult, delete, func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..core.settings import settings
from ..core.permissions import ADMIN
from ..core.users import new_user
from ..models.dividend_models import Dividend
from ..models.settings_models import ROLE_GRANTS_TABLE
from ..models.stock_models import Stock
from ..models.transaction_models import Transaction, TypeEnum
from ..models.user_models import User

DEMO_USERS: dict[str, str] = {"demo-admin": "demo-admin-pass", "demo-user": "demo-user-pass"}
"""Dev-only logins (user id → password)."""

DEMO_ADMIN = "demo-admin"
"""Granted the admin role (a gth_role_grants row), as if assigned at
/admin/roles, so the admin pages work without a ROLE_BOOTSTRAP."""

MARKET = "ASX"
DIVIDEND_SOURCE = "demo"


@dataclass(frozen=True)
class DemoStock:
    symbol: str
    name: str
    base_price: Decimal
    archived_on: Optional[date] = None  # sold out before this date, then archived


DEMO_STOCKS: tuple[DemoStock, ...] = (
    DemoStock("BHP", "BHP Group Limited", Decimal("44.00")),
    DemoStock("CBA", "Commonwealth Bank of Australia", Decimal("120.00")),
    DemoStock("CSL", "CSL Limited", Decimal("285.00")),
    DemoStock("WES", "Wesfarmers Limited", Decimal("62.00")),
    DemoStock("WOW", "Woolworths Group Limited", Decimal("33.00")),
    DemoStock("NAB", "National Australia Bank Limited", Decimal("33.50")),
    DemoStock("TLS", "Telstra Group Limited", Decimal("3.95"), archived_on=date(2024, 11, 29)),
    DemoStock("FMG", "Fortescue Ltd", Decimal("21.50"), archived_on=date(2025, 3, 31)),
)

# Transactions per demo user, over FY2023-24 .. FY2025-26.
TRANSACTION_COUNTS: dict[str, int] = {"demo-admin": 100, "demo-user": 50}
PERIOD_START = date(2023, 7, 1)
PERIOD_END = date(2026, 6, 30)
NOTES = ("DRP top-up", "Rebalance", "Averaging down", "Took some profit", "Tax-loss sale",
         "Bought the dip", "Quarterly contribution", "Trimmed position")
RANDOM_SEED = 20260702


class DemoSeedRefused(RuntimeError):
    """seed_demo was asked to run outside ENVIRONMENT == "development"."""


@dataclass
class SeedSummary:
    users_created: int = 0
    grants_created: int = 0
    stocks_created: int = 0
    transactions_created: int = 0
    dividends_created: int = 0
    reset: dict[str, int] = field(default_factory=dict)

    @property
    def created_anything(self) -> bool:
        return any((self.users_created, self.grants_created, self.stocks_created,
                    self.transactions_created, self.dividends_created))


async def seed_demo(session: AsyncSession, *, reset: bool = False,
                    environment: Optional[str] = None) -> SeedSummary:
    """Create the demo rows that don't exist yet (see the module docstring)
    and commit. With reset=True, delete the seed's own rows first."""
    environment = settings.environment if environment is None else environment
    if environment != "development":
        raise DemoSeedRefused(
            f"demo data is for development only (ENVIRONMENT is {environment!r})")
    summary = SeedSummary()
    if reset:
        summary.reset = await _reset(session)
    users = await _ensure_users(session, summary)
    await _ensure_admin_grant(session, summary)
    stocks = await _ensure_stocks(session, summary)
    for user_id, count in TRANSACTION_COUNTS.items():
        await _ensure_transactions(session, users[user_id], stocks, count, summary)
    await _ensure_dividends(session, stocks, summary)
    await session.commit()
    return summary


async def _reset(session: AsyncSession) -> dict[str, int]:
    ids = list(DEMO_USERS)
    # Explicit, not relying on the FK cascade: SQLite only enforces it with
    # PRAGMA foreign_keys on.
    txns = await session.execute(
        delete(Transaction).where(col(Transaction.user_id).in_(ids)))
    users = await session.execute(delete(User).where(col(User.id).in_(ids)))
    grants = await session.execute(
        delete(ROLE_GRANTS_TABLE).where(ROLE_GRANTS_TABLE.c.subject.in_(ids)))
    dividends = await session.execute(
        delete(Dividend).where(col(Dividend.source) == DIVIDEND_SOURCE))
    stocks_removed = 0
    for demo in DEMO_STOCKS:
        stock = await Stock.search(session, market=MARKET, symbol=demo.symbol)
        if stock is None:
            continue
        refs = (await session.exec(select(func.count()).select_from(Transaction).where(
            Transaction.stock_id == stock.id))).one()
        refs += (await session.exec(select(func.count()).select_from(Dividend).where(
            Dividend.stock_id == stock.id))).one()
        if refs == 0:
            await session.delete(stock)
            stocks_removed += 1
    await session.flush()
    return {"transactions": cast(CursorResult, txns).rowcount,
            "grants": cast(CursorResult, grants).rowcount,
            "users": cast(CursorResult, users).rowcount,
            "dividends": cast(CursorResult, dividends).rowcount, "stocks": stocks_removed}


async def _ensure_users(session: AsyncSession, summary: SeedSummary) -> dict[str, User]:
    users = {}
    for user_id, password in DEMO_USERS.items():
        user = await session.get(User, user_id)
        if user is None:
            user = new_user(user_id, password)
            session.add(user)
            summary.users_created += 1
        users[user_id] = user
    await session.flush()
    return users


async def _ensure_admin_grant(session: AsyncSession, summary: SeedSummary) -> None:
    table = ROLE_GRANTS_TABLE
    found = (await session.exec(select(table.c.role).where(
        table.c.subject == DEMO_ADMIN, table.c.role == ADMIN.name))).first()
    if found is None:
        await session.execute(table.insert().values(subject=DEMO_ADMIN, role=ADMIN.name))
        summary.grants_created += 1


async def _ensure_stocks(session: AsyncSession, summary: SeedSummary) -> dict[str, Stock]:
    stocks = {}
    for demo in DEMO_STOCKS:
        stock = await Stock.search(session, market=MARKET, symbol=demo.symbol)
        if stock is None:
            stock = Stock(symbol=demo.symbol, market=MARKET, name=demo.name)
            if demo.archived_on:
                stock.is_active = False
                stock.archived_at = datetime.combine(demo.archived_on, datetime.min.time(),
                                                     tzinfo=timezone.utc)
            session.add(stock)
            summary.stocks_created += 1
        stocks[demo.symbol] = stock
    await session.flush()
    return stocks


def _price(rng: random.Random, demo: DemoStock) -> Decimal:
    return (demo.base_price * Decimal(str(rng.uniform(0.85, 1.15)))).quantize(Decimal("0.01"))


async def _ensure_transactions(session: AsyncSession, user: User, stocks: dict[str, Stock],
                               count: int, summary: SeedSummary) -> None:
    existing = (await session.exec(select(func.count()).select_from(Transaction).where(
        Transaction.user_id == user.id))).one()
    if existing:
        return  # this demo user already has their history
    rng = random.Random(f"{RANDOM_SEED}:{user.id}")
    span = (PERIOD_END - PERIOD_START).days
    dates = sorted(PERIOD_START + timedelta(days=rng.randrange(span + 1)) for _ in range(count))
    held: dict[str, Decimal] = {d.symbol: Decimal(0) for d in DEMO_STOCKS}
    rows: list[Transaction] = []
    user_id = user.id
    assert user_id is not None  # a primary key, set when the user was created

    def add(demo: DemoStock, on: date, kind: TypeEnum, units: Decimal, note: Optional[str] = None) -> None:
        stock_id = stocks[demo.symbol].id
        assert stock_id is not None  # flushed in _ensure_stocks
        rows.append(Transaction(
            user_id=user_id, stock_id=stock_id, transaction_date=on, type=kind,
            units=units, price=_price(rng, demo), fees=rng.choice((Decimal("9.95"), Decimal("19.95"))),
            notes=note))
        held[demo.symbol] += units if kind is TypeEnum.BUY else -units

    for on in dates:
        tradable = [d for d in DEMO_STOCKS if d.archived_on is None or on < d.archived_on]
        demo = rng.choice(tradable)
        note = rng.choice(NOTES) if rng.random() < 0.06 else None
        if held[demo.symbol] > 0 and rng.random() < 0.3:
            units = max(Decimal(1), (held[demo.symbol] * Decimal(str(rng.uniform(0.2, 0.8)))).quantize(Decimal(1)))
            add(demo, on, TypeEnum.SELL, min(units, held[demo.symbol]), note)
        else:
            add(demo, on, TypeEnum.BUY, Decimal(rng.randrange(10, 501)), note)
    # An archived stock was sold out the day before it was archived.
    for demo in DEMO_STOCKS:
        if demo.archived_on and held[demo.symbol] > 0:
            add(demo, demo.archived_on - timedelta(days=1), TypeEnum.SELL, held[demo.symbol], "Sold out")
    session.add_all(rows)
    await session.flush()
    summary.transactions_created += len(rows)


def _dividend_dates() -> list[date]:
    days = [date(y, m, 20) for y in range(PERIOD_START.year, PERIOD_END.year + 1) for m in (2, 8)]
    return [d for d in days if PERIOD_START <= d <= PERIOD_END]


async def _ensure_dividends(session: AsyncSession, stocks: dict[str, Stock], summary: SeedSummary) -> None:
    for demo in DEMO_STOCKS:
        if demo.archived_on:
            continue
        stock = stocks[demo.symbol]
        assert stock.id is not None  # flushed in _ensure_stocks
        for ex_date in _dividend_dates():
            found = (await session.exec(select(Dividend).where(
                Dividend.stock_id == stock.id, Dividend.ex_date == ex_date))).first()
            if found is not None:
                continue
            session.add(Dividend(
                stock_id=stock.id, ex_date=ex_date, pay_date=ex_date + timedelta(days=21),
                amount_per_share=(demo.base_price * Decimal("0.015")).quantize(Decimal("0.01")),
                source=DIVIDEND_SOURCE))
            summary.dividends_created += 1
    await session.flush()


async def _run(reset: bool) -> SeedSummary:
    from ..db.session import _get_engine, init_db

    await init_db()
    _, session_maker = _get_engine()
    async with session_maker() as session:
        return await seed_demo(session, reset=reset)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Seed PyFinBot with demo data (development only).")
    parser.add_argument("--reset", action="store_true", help="delete the demo rows first, then seed")
    args = parser.parse_args(argv)
    if settings.environment != "development":
        print(f"Refusing: demo data is for development only (ENVIRONMENT is {settings.environment!r}).",
              file=sys.stderr)
        return 2
    summary = asyncio.run(_run(args.reset))
    if summary.reset:
        print("Reset: " + ", ".join(f"{n} {what}" for what, n in summary.reset.items()))
    print(f"Created {summary.users_created} users, {summary.stocks_created} stocks, "
          f"{summary.transactions_created} transactions, {summary.dividends_created} dividends"
          + ("" if summary.created_anything else " (already seeded)") + ".")
    print("Log in as: " + ", ".join(f"{u} / {p}" for u, p in DEMO_USERS.items())
          + f" ({DEMO_ADMIN} has the admin role).")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
