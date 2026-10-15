"""fetch_commsec_emails is core's ImapReader.fetch with the Commsec criteria
(core v0.14's fetch leaves out a message deleted since the search, tested
there)."""
from unittest.mock import patch

import pytest
from greentechhub_core.email import IMAPConfig

from pyfinbot.core.email_sync import EmailAccount, EmailNotConfiguredError, fetch_commsec_emails

CONFIG = IMAPConfig(host="imap.example.com", username="me@example.com", password="secret")
ACCOUNT = EmailAccount(imap=CONFIG)


def test_fetch_searches_unseen_commsec_mail_through_cores_reader():
    with patch("pyfinbot.core.email_sync.ImapReader") as reader:
        reader.return_value.fetch.return_value = [(b"1", "message")]
        messages = fetch_commsec_emails(ACCOUNT)
    reader.assert_called_once_with(CONFIG)
    reader.return_value.fetch.assert_called_once_with('(UNSEEN FROM "bounceback@commsec.com.au")')
    assert messages == [(b"1", "message")]


def test_fetch_can_include_seen_mail():
    with patch("pyfinbot.core.email_sync.ImapReader") as reader:
        fetch_commsec_emails(ACCOUNT, only_unseen=False)
    reader.return_value.fetch.assert_called_once_with('(FROM "bounceback@commsec.com.au")')


def test_fetch_without_a_mailbox_raises_before_connecting():
    with patch("pyfinbot.core.email_sync.ImapReader") as reader, pytest.raises(EmailNotConfiguredError):
        fetch_commsec_emails(EmailAccount())
    reader.assert_not_called()
