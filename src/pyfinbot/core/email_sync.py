"""IMAP fetch for Commsec trade confirmation emails, from one user's own
mailbox (their EmailAccount, from their Settings — see core/email_accounts.py).
The generic IMAP half is greentechhub-core's (IMAPConfig, ImapReader,
message_text, received_at); the Commsec sender criteria live here."""
from __future__ import annotations

from dataclasses import dataclass
from email.message import Message
from typing import List, Optional, Tuple

from greentechhub_core.email import IMAPConfig, ImapReader, message_text, received_at

__all__ = [
    "COMMSEC_SENDER",
    "NOT_CONFIGURED",
    "EmailAccount",
    "GmailNotConfiguredError",
    "commsec_criteria",
    "fetch_commsec_emails",
    "mark_seen",
    "message_text",
    "received_at",
]

NOT_CONFIGURED = "Set your email address and app password in Settings to sync Commsec emails."
COMMSEC_SENDER = "bounceback@commsec.com.au"


class GmailNotConfiguredError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmailAccount:
    """One user's mailbox: core's IMAPConfig (None until the address and app
    password are both set; its password is kept out of repr, and never put in
    a template) and the sender Commsec confirmations come from."""

    imap: Optional[IMAPConfig] = None
    commsec_sender: str = COMMSEC_SENDER

    @property
    def configured(self) -> bool:
        return self.imap is not None


def commsec_criteria(account: EmailAccount, *, only_unseen: bool = True) -> str:
    """The IMAP search for `account`'s Commsec confirmations."""
    unseen = "UNSEEN " if only_unseen else ""
    return f'({unseen}FROM "{account.commsec_sender}")'


def _config(account: EmailAccount) -> IMAPConfig:
    if account.imap is None:
        raise GmailNotConfiguredError(NOT_CONFIGURED)
    return account.imap


def fetch_commsec_emails(account: EmailAccount, *, only_unseen: bool = True) -> List[Tuple[bytes, Message]]:
    """
    `account`'s Commsec confirmations (UNSEEN only by default) as (uid,
    email.message.Message) pairs. Synchronous — run via asyncio.to_thread.
    Does NOT mark messages \\Seen; call mark_seen() after successful
    processing so a partially-failed sync can be safely retried.
    """
    return ImapReader(_config(account)).fetch(commsec_criteria(account, only_unseen=only_unseen))


def mark_seen(account: EmailAccount, uids: List[bytes]) -> None:
    """Mark the given message UIDs \\Seen in `account`'s mailbox after a
    successful sync."""
    ImapReader(_config(account)).mark_seen(uids)
