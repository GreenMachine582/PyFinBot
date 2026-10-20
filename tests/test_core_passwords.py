"""Password hashing comes from greentechhub_core.security: hash_password /
verify_password replace core/security.py's bcrypt helpers. Same bcrypt
$2b$ format, so passwords hashed before the switch still verify."""
import importlib.util
from pathlib import Path

import bcrypt
from greentechhub_core.security import hash_password, verify_password

import pyfinbot
from .conftest import insert_account, post_login

HTML = {"Accept": "text/html"}


def _old_hash(password: str) -> str:
    """Exactly what the deleted pyfinbot.core.security.hash_password stored."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def test_pyfinbot_no_longer_hashes_passwords_itself():
    # core/security.py itself is gone too (its API tokens are fastapi's issue_token).
    assert importlib.util.find_spec("pyfinbot.core.security") is None
    src = Path(pyfinbot.__file__).parent
    assert not [p for p in src.rglob("*.py") if "import bcrypt" in p.read_text(encoding="utf-8")]


def test_a_hash_from_before_the_switch_still_verifies():
    stored = _old_hash("hunter2!")
    assert verify_password("hunter2!", stored)
    assert not verify_password("hunter3!", stored)
    # And new hashes are the same scheme.
    assert hash_password("x").startswith("$2b$12$") and stored.startswith("$2b$12$")


async def _store_user(username: str, password_hash: str) -> None:
    from greentechhub_fastapi.auth import resolve_dependency

    from pyfinbot.db.session import get_session
    from pyfinbot.pyfinbot import app

    async with resolve_dependency(app, get_session) as session:
        await insert_account(session, username, password_hash=password_hash)
        await session.commit()


async def test_a_user_with_an_old_hash_still_logs_in(gth_client):
    await _store_user("old-hash", _old_hash("hunter2!"))
    api = await gth_client.post("/api/auth/login", data={"username": "old-hash", "password": "hunter2!"})
    assert api.status_code == 200 and api.json()["access_token"]
    web = await post_login(gth_client, "old-hash", "hunter2!", follow_redirects=False)
    assert web.status_code == 303 and web.headers["location"] == "/"


async def test_a_malformed_stored_hash_is_a_failed_login_not_a_500(gth_client):
    await _store_user("bad-hash", "not-a-bcrypt-hash")
    api = await gth_client.post("/api/auth/login", data={"username": "bad-hash", "password": "hunter2!"})
    assert api.status_code == 401 and api.json()["code"] == "unauthorized"
    web = await post_login(gth_client, "bad-hash", "hunter2!", headers=HTML)
    assert web.status_code == 401
