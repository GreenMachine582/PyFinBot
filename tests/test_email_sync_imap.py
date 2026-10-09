"""The IMAP half of core/email_sync.py against a fake IMAP4_SSL: fetch skips a
message gone since the search, and mark_seen goes through core's ImapReader.
Reading a message's body is core's message_text (tested there)."""
from unittest.mock import MagicMock, patch

from greentechhub_core.email import IMAPConfig

from pyfinbot.core.email_sync import EmailAccount, fetch_commsec_emails, mark_seen

CONFIG = IMAPConfig(host="imap.example.com", username="me@example.com", password="secret")
ACCOUNT = EmailAccount(imap=CONFIG)
RAW = b"From: bounceback@commsec.com.au\r\nSubject: Confirmation\r\n\r\nBOUGHT 10 CBA\r\n"


def _fake_imap(fetch_results: dict[bytes, list]) -> MagicMock:
    imap = MagicMock()
    imap.search.return_value = ("OK", [b" ".join(fetch_results)])
    imap.fetch.side_effect = lambda uid, _spec: ("OK", fetch_results[uid])
    return imap


def test_fetch_parses_each_message():
    imap = _fake_imap({b"1": [(b"1 (RFC822 {80}", RAW), b")"]})
    with patch("pyfinbot.core.email_sync.imaplib.IMAP4_SSL", return_value=imap):
        messages = fetch_commsec_emails(ACCOUNT)
    assert [(uid, msg["Subject"]) for uid, msg in messages] == [(b"1", "Confirmation")]
    imap.logout.assert_called_once()


def test_fetch_skips_a_message_deleted_since_the_search():
    imap = _fake_imap({b"1": [None], b"2": [(b"2 (RFC822 {80}", RAW), b")"]})
    with patch("pyfinbot.core.email_sync.imaplib.IMAP4_SSL", return_value=imap):
        messages = fetch_commsec_emails(ACCOUNT)
    assert [uid for uid, _ in messages] == [b"2"]


def test_mark_seen_uses_cores_reader():
    with patch("pyfinbot.core.email_sync.ImapReader") as reader:
        mark_seen(ACCOUNT, [b"7", b"9"])
    reader.assert_called_once_with(CONFIG)
    reader.return_value.mark_seen.assert_called_once_with([b"7", b"9"])
