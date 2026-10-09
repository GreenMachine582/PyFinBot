"""Commsec email sync on greentechhub-core's IMAP pieces (v0.13): the Email
sync settings are core's imap_settings plus the Commsec sender, the mailbox
is core's IMAPConfig, and bodies are read with core's message_text."""
import email
from email.message import EmailMessage
from pathlib import Path

import pytest
from greentechhub_core.email import IMAPConfig

from pyfinbot.core.commsec_parser import parse_commsec_email
from pyfinbot.core.email_sync import (
    COMMSEC_SENDER,
    EmailAccount,
    GmailNotConfiguredError,
    commsec_criteria,
    fetch_commsec_emails,
    mark_seen,
    message_text,
    received_at,
)
from pyfinbot.core.user_settings import EMAIL_GROUP, USER_SETTINGS

FIXTURE = Path(__file__).parent / "fixtures" / "commsec_emails" / "bought_rmd.txt"
EMAIL_KEYS = ("email.address", "email.app_password", "email.imap_host", "email.imap_port", "email.mailbox",
              "email.commsec_sender")


def _settings():
    return {s.key: s for s in USER_SETTINGS if s.group == EMAIL_GROUP}


def test_email_sync_settings_are_cores_imap_settings_plus_the_sender():
    settings = _settings()
    assert tuple(settings) == EMAIL_KEYS
    assert settings["email.app_password"].secret
    assert "Google App Password" in settings["email.app_password"].help_text
    assert "Commsec" in settings["email.address"].help_text
    assert settings["email.commsec_sender"].default == COMMSEC_SENDER


def test_commsec_criteria():
    account = EmailAccount(commsec_sender="trades@example.com")
    assert commsec_criteria(account) == '(UNSEEN FROM "trades@example.com")'
    assert commsec_criteria(account, only_unseen=False) == '(FROM "trades@example.com")'


def test_an_unset_mailbox_is_not_configured():
    account = EmailAccount()
    assert not account.configured
    with pytest.raises(GmailNotConfiguredError):
        fetch_commsec_emails(account)
    with pytest.raises(GmailNotConfiguredError):
        mark_seen(account, [b"1"])
    assert EmailAccount(imap=IMAPConfig(host="h", username="u", password="p")).configured


def test_an_html_only_confirmation_parses_like_the_plain_one():
    plain = email.message_from_string(FIXTURE.read_text(encoding="utf-8"))
    paragraphs = [p for p in plain.get_payload().split("\n\n") if p.strip()]
    html = EmailMessage()
    html["Subject"], html["Date"] = plain["Subject"], plain["Date"]
    html.set_content("<html><head><style>p {color: red}</style></head><body><table><tr><td>"
                     + "".join(f"<p>{p}</p>" for p in paragraphs) + "</td></tr></table></body></html>",
                     subtype="html")

    expected = parse_commsec_email(plain["Subject"], message_text(plain), received_at(plain))
    assert parse_commsec_email(html["Subject"], message_text(html), received_at(html)) == expected
