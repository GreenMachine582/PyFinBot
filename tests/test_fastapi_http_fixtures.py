"""The HTTP test fixtures are greentechhub-fastapi's (testing, v0.16):
gth_client and client_as on PyFinBot's app (gth_app) and Database (gth_db),
with the app's dependency_overrides restored after each test rather than
cleared, so register_auth's adapter survives."""
from pyfinbot.pyfinbot import app

from .conftest import account_row, web_login


async def test_client_as_signs_in_through_the_web_form(client_as):
    alice = await client_as("http-alice")
    page = await alice.get("/", follow_redirects=False)
    assert page.status_code == 200


async def test_a_user_made_for_the_client_is_in_the_test_database(gth_create_user, gth_client, gth_session):
    await gth_create_user("http-bob", "hunter2!")
    assert await account_row(gth_session, "http-bob") is not None


async def test_a_test_may_override_a_dependency(gth_client):
    def nobody():
        return None

    app.dependency_overrides[nobody] = nobody


async def test_overrides_are_restored_and_the_auth_adapter_survives(gth_client):
    assert not any(getattr(k, "__name__", "") == "nobody" for k in app.dependency_overrides)
    # Pages resolve the signed-in user through register_auth's override of
    # get_current_user; were it cleared, this would fail instead of render.
    await web_login(gth_client, "http-carol")
    assert (await gth_client.get("/", follow_redirects=False)).status_code == 200
