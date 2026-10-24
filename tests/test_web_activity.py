"""The dashboard's activity feed (greentechhub-ui v0.20's gth_timeline over
gth_audit_log): a user sees only their own entries, newest first, ten at a
time, with "Load older" fetching the rest from /activity."""
import io
from datetime import UTC, datetime, timedelta

from greentechhub_core.audit import new_entry

from pyfinbot.core.activity import ACTIVITY_PAGE_SIZE
from pyfinbot.pyfinbot import AUDIT_STORE

from .conftest import create_stock, user_id, web_login

HX = {"HX-Request": "true"}
CSV = "date,stock,type,units,price,fees,notes\n2024-08-01,ASX:ACT,Buy,10,20,0,\n2024-08-02,ASX:NOPE,Buy,1,1,0,\n"
START = datetime(2020, 1, 1, 9, 0, tzinfo=UTC)


async def _record(username: str, count: int) -> None:
    """`count` stock syncs by `username`, an hour apart from START, so
    "sync 0" is the oldest. Dated years back so a sign-in's entry (now)
    is always newer."""
    actor = await user_id(username)
    for n in range(count):
        await AUDIT_STORE.record(new_entry("stocks.market_synced", actor=actor, summary=f"sync {n}",
                                           now=START + timedelta(hours=n)))


async def test_an_import_shows_on_the_dashboard_as_yours(gth_client):
    await web_login(gth_client, "activity-import")
    await create_stock(gth_client, "ACT", "ASX", "Activity Co")
    resp = await gth_client.post("/import", headers=HX,
                                 files={"file": ("t.csv", io.BytesIO(CSV.encode()), "text/csv")})
    assert resp.status_code == 200, resp.text
    page = (await gth_client.get("/")).text
    assert "Recent activity" in page and "gth-timeline" in page
    assert "Imported 1 of 2 rows from t.csv" in page
    assert "You" in page and await user_id("activity-import") not in page


async def test_another_users_entries_never_show(gth_client):
    await web_login(gth_client, "activity-other")
    await _record("activity-other", 1)
    await web_login(gth_client, "activity-me")
    assert "sync 0" not in (await gth_client.get("/")).text
    assert "sync 0" not in (await gth_client.get("/activity", params={"before": "2099-01-01"})).text


async def test_load_older_pages_back_without_the_shell(gth_client):
    await web_login(gth_client, "activity-pages")
    await _record("activity-pages", ACTIVITY_PAGE_SIZE + 2)
    page = (await gth_client.get("/")).text
    # The sign-in, then the 9 newest syncs: syncs 11 down to 3 fill the first page.
    assert "sync 11" in page and "sync 3" in page and "sync 2" not in page
    assert "Load older" in page and "/activity?before=" in page

    cursor = (START + timedelta(hours=3)).isoformat()
    older = await gth_client.get("/activity", params={"before": cursor}, headers=HX)
    assert older.status_code == 200
    assert "sync 2" in older.text and "sync 0" in older.text and "sync 3" not in older.text
    assert "<html" not in older.text and "Load older" not in older.text


async def test_an_unreadable_cursor_gives_the_first_page(gth_client):
    await web_login(gth_client, "activity-cursor")
    await _record("activity-cursor", 1)
    resp = await gth_client.get("/activity", params={"before": "not-a-date"}, headers=HX)
    assert resp.status_code == 200 and "sync 0" in resp.text


async def test_a_new_user_sees_their_sign_in(gth_client):
    await web_login(gth_client, "activity-new")
    page = (await gth_client.get("/")).text
    assert "Recent activity" in page and "auth.signed_in" in page


async def test_activity_needs_a_sign_in(gth_client):
    resp = await gth_client.get("/activity", follow_redirects=False)
    assert resp.status_code in (302, 303, 307) and "/login" in resp.headers["location"]


def test_the_feed_is_empty_without_entries():
    from pyfinbot.web.templating import templates

    html = templates.env.from_string(
        '{% from "timeline.html" import gth_timeline %}'
        '{{ gth_timeline([], empty_message="No activity yet — imports and syncs show up here.") }}'
    ).render()
    assert "No activity yet — imports and syncs show up here." in html
