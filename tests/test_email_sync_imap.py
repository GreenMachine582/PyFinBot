"""The IMAP half of core/email_sync.py: mark_seen goes through core's
ImapReader. Fetching is tested in test_email_sync_core_fetch.py, and reading a
message's body is core's message_text (tested there)."""
from unittest.mock import patch

from greentechhub_core.email import IMAPConfig

from pyfinbot.core.email_sync import EmailAccount, mark_seen

CONFIG = IMAPConfig(host="imap.example.com", username="me@example.com", password="secret")
ACCOUNT = EmailAccount(imap=CONFIG)


def test_mark_seen_uses_cores_reader():
    with patch("pyfinbot.core.email_sync.ImapReader") as reader:
        mark_seen(ACCOUNT, [b"7", b"9"])
    reader.assert_called_once_with(CONFIG)
    reader.return_value.mark_seen.assert_called_once_with([b"7", b"9"])
