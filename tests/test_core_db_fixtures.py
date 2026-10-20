"""The test database is greentechhub-core's (testing.sqlalchemy, v0.14):
each test runs inside a rolled-back transaction, and with gth_db set
gth_client points the app's Database at it (gth_database)."""
from sqlmodel import select

from pyfinbot.db.session import db, get_session
from pyfinbot.models.stock_models import Stock

from .conftest import account_row, insert_account

USERNAME = "fixture-isolation"


async def test_a_committed_row_is_seen_within_its_test(gth_session):
    await insert_account(gth_session, USERNAME)
    await gth_session.commit()
    assert await account_row(gth_session, USERNAME) is not None


async def test_it_is_rolled_back_before_the_next_test(gth_session):
    assert await account_row(gth_session, USERNAME) is None


async def test_the_client_uses_the_test_sessionmaker(gth_client, gth_sessionmaker):
    assert db.sessionmaker() is gth_sessionmaker


async def test_closing_get_session_ends_its_session_at_once(gth_client):
    """FastAPI closes get_session after the response. Its db.session() must
    close then too, not when it's collected: until then its SAVEPOINT stays
    open and the next session's nests inside it."""
    sessions = get_session()
    session = await anext(sessions)
    await session.exec(select(Stock))
    assert session.in_transaction()
    await sessions.aclose()
    assert not session.in_transaction()
