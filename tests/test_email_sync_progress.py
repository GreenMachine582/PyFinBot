"""sync_commsec_emails reports progress(phase, done, total): "reading" while
the mailbox is searched, then "importing" once per email, a skipped one
included."""
from email.message import Message

from pyfinbot.core.commsec_import import sync_commsec_emails
from pyfinbot.core.email_sync import EmailAccount

from .conftest import insert_account
from .test_email_sync import _fake_messages


async def test_sync_reports_reading_then_importing(gth_session):
    owner = await insert_account(gth_session, "progress-owner")
    unparseable = Message()
    unparseable["Subject"] = "Not a trade confirmation"
    messages = [*_fake_messages("bought_rmd.txt"), (b"9", unparseable)]
    calls = []

    summary = await sync_commsec_emails(
        gth_session, owner, EmailAccount(),
        fetch=lambda account, *, only_unseen: messages, mark=lambda account, uids: None,
        progress=lambda *call: calls.append(call))

    assert (summary.created, summary.skipped) == (1, 1)
    assert calls == [("reading", 0, 0), ("importing", 0, 2), ("importing", 1, 2), ("importing", 2, 2)]


async def test_sync_without_progress_still_runs(gth_session):
    summary = await sync_commsec_emails(
        gth_session, await insert_account(gth_session, "progress-none"), EmailAccount(),
        fetch=lambda account, *, only_unseen: [], mark=lambda account, uids: None)
    assert summary.total_emails == 0
