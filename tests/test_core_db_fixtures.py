"""The test database is greentechhub-core's (testing.sqlalchemy, v0.14):
each test runs inside a rolled-back transaction, and the client fixture
points the app's Database at it with gth_database(db)."""
from sqlmodel import select

from pyfinbot.db.session import db, get_session
from pyfinbot.models.user_models import User

USER_ID = "fixture-isolation"


async def test_a_committed_row_is_seen_within_its_test(gth_session):
    gth_session.add(User(id=USER_ID, active=True, password_hash="x"))
    await gth_session.commit()
    assert (await gth_session.exec(select(User).where(User.id == USER_ID))).first() is not None


async def test_it_is_rolled_back_before_the_next_test(gth_session):
    assert (await gth_session.exec(select(User).where(User.id == USER_ID))).first() is None


async def test_the_client_uses_the_test_sessionmaker(client, gth_sessionmaker):
    assert db.sessionmaker() is gth_sessionmaker


async def test_closing_get_session_ends_its_session_at_once(client):
    """FastAPI closes get_session after the response. Its db.session() must
    close then too, not when it's collected: until then its SAVEPOINT stays
    open and the next session's nests inside it."""
    sessions = get_session()
    session = await anext(sessions)
    await session.exec(select(User))
    assert session.in_transaction()
    await sessions.aclose()
    assert not session.in_transaction()
