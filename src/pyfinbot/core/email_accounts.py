"""Each user's email account for Commsec sync, from their own settings (the
"Email sync" group in core/user_settings.py: core's imap_settings plus the
Commsec sender). The app password is a greentechhub secret setting:
encrypted at rest, write-only on /settings, read back here by core's
imap_config for the IMAP login only."""

from dataclasses import dataclass

from greentechhub_core.email import imap_config
from greentechhub_core.settings import SecretDecryptError, Settings

from .commsec_import import EmailSyncError
from .email_sync import EmailAccount

UNREADABLE_PASSWORD = (
    "Your saved app password can't be read (the server's encryption key changed). "
    "Enter it again in Settings."
)


@dataclass(frozen=True)
class _Subject:
    subject: str


async def load_email_account(settings: Settings, subject: str) -> EmailAccount:
    """`subject`'s EmailAccount (their mailbox, None until set up, and the
    Commsec sender). Raises EmailSyncError (503) when the saved password no
    longer decrypts."""
    who = _Subject(subject)
    try:
        imap = await imap_config(settings, who)
    except SecretDecryptError:
        raise EmailSyncError(503, UNREADABLE_PASSWORD) from None
    return EmailAccount(imap=imap, commsec_sender=str(await settings.get("email.commsec_sender", who)))
