"""IMAP fetch for Commsec trade confirmation emails, from one user's own
mailbox (their EmailAccount, from their Settings — see core/email_accounts.py)."""
from __future__ import annotations

import email
import imaplib
from dataclasses import dataclass, field
from datetime import datetime
from email.message import Message
from email.utils import parsedate_to_datetime
from typing import List, Tuple

from bs4 import BeautifulSoup

NOT_CONFIGURED = "Set your email address and app password in Settings to sync Commsec emails."


class GmailNotConfiguredError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmailAccount:
    """One user's mailbox. app_password is the plaintext from
    Settings.get_secret: kept out of repr, and never put in a template."""

    address: str = ""
    app_password: str = field(default="", repr=False)
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    mailbox: str = "INBOX"
    commsec_sender: str = "bounceback@commsec.com.au"

    @property
    def configured(self) -> bool:
        return bool(self.address and self.app_password)


def fetch_commsec_emails(account: EmailAccount, *, only_unseen: bool = True) -> List[Tuple[bytes, Message]]:
    """
    Connect to `account`'s mailbox over IMAP (App Password auth), search its
    `mailbox` for messages from its `commsec_sender` (UNSEEN only by default),
    return (uid, email.message.Message) pairs. Synchronous — run via
    asyncio.to_thread. Does NOT mark messages \\Seen; call mark_seen() after
    successful processing so a partially-failed sync can be safely retried.
    """
    if not account.configured:
        raise GmailNotConfiguredError(NOT_CONFIGURED)

    imap = imaplib.IMAP4_SSL(account.imap_host, account.imap_port)
    try:
        imap.login(account.address, account.app_password)
        imap.select(account.mailbox)
        criteria = f'(FROM "{account.commsec_sender}")'
        if only_unseen:
            criteria = f'(UNSEEN FROM "{account.commsec_sender}")'
        _, data = imap.search(None, criteria)
        messages: List[Tuple[bytes, Message]] = []
        for uid in data[0].split():
            _, msg_data = imap.fetch(uid, "(RFC822)")
            messages.append((uid, email.message_from_bytes(msg_data[0][1])))
        return messages
    finally:
        imap.logout()


def extract_body(msg: Message) -> str:
    """Prefer text/plain; fall back to BeautifulSoup-stripped text/html —
    Commsec confirmation emails may be multipart with an HTML-only body."""
    plain, html = None, None
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain" and plain is None:
                payload = part.get_payload(decode=True)
                if payload:
                    plain = payload.decode(errors="replace")
            elif ctype == "text/html" and html is None:
                payload = part.get_payload(decode=True)
                if payload:
                    html = payload.decode(errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            text = payload.decode(errors="replace")
            if msg.get_content_type() == "text/html":
                html = text
            else:
                plain = text
    if plain and plain.strip():
        return plain
    if html:
        return BeautifulSoup(html, "html.parser").get_text(separator=" ")
    return ""


def received_at(msg: Message) -> datetime:
    """Parse the message's Date header — stands in for trade date, since
    Commsec confirmation emails don't state one explicitly and are sent
    promptly after the trade."""
    date_header = msg.get("Date")
    if not date_header:
        raise ValueError("Message has no Date header")
    return parsedate_to_datetime(date_header)


def mark_seen(account: EmailAccount, uids: List[bytes]) -> None:
    """Mark the given message UIDs \\Seen in `account`'s mailbox after a
    successful sync."""
    if not uids:
        return
    imap = imaplib.IMAP4_SSL(account.imap_host, account.imap_port)
    try:
        imap.login(account.address, account.app_password)
        imap.select(account.mailbox)
        for uid in uids:
            imap.store(uid, "+FLAGS", "\\Seen")
    finally:
        imap.logout()
