"""IMAP-based Gmail fetch for Commsec trade confirmation emails."""
from __future__ import annotations

import email
import imaplib
from datetime import datetime
from email.message import Message
from email.utils import parsedate_to_datetime
from typing import List, Tuple

from bs4 import BeautifulSoup

from .settings import settings


class GmailNotConfiguredError(RuntimeError):
    pass


def fetch_commsec_emails(*, only_unseen: bool = True) -> List[Tuple[bytes, Message]]:
    """
    Connect to Gmail via IMAP (App Password auth), search `GMAIL_MAILBOX` for
    messages from `COMMSEC_SENDER` (UNSEEN only by default), return
    (uid, email.message.Message) pairs. Synchronous — run via asyncio.to_thread.
    Does NOT mark messages \\Seen; call mark_seen() after successful processing
    so a partially-failed sync can be safely retried.
    """
    if not settings.GMAIL_ADDRESS or not settings.GMAIL_APP_PASSWORD:
        raise GmailNotConfiguredError("GMAIL_ADDRESS/GMAIL_APP_PASSWORD not configured")

    imap = imaplib.IMAP4_SSL(settings.GMAIL_IMAP_HOST, settings.GMAIL_IMAP_PORT)
    try:
        imap.login(settings.GMAIL_ADDRESS, settings.GMAIL_APP_PASSWORD)
        imap.select(settings.GMAIL_MAILBOX)
        criteria = f'(FROM "{settings.COMMSEC_SENDER}")'
        if only_unseen:
            criteria = f'(UNSEEN FROM "{settings.COMMSEC_SENDER}")'
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


def mark_seen(uids: List[bytes]) -> None:
    """Mark the given message UIDs \\Seen after a successful sync."""
    if not uids:
        return
    imap = imaplib.IMAP4_SSL(settings.GMAIL_IMAP_HOST, settings.GMAIL_IMAP_PORT)
    try:
        imap.login(settings.GMAIL_ADDRESS, settings.GMAIL_APP_PASSWORD)
        imap.select(settings.GMAIL_MAILBOX)
        for uid in uids:
            imap.store(uid, "+FLAGS", "\\Seen")
    finally:
        imap.logout()
