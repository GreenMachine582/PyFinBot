"""Each user's email account for Commsec sync, from their own settings (the
"Email sync" group in core/user_settings.py). The app password is a
greentechhub secret setting: encrypted at rest, write-only on /settings,
read back here with Settings.get_secret for the IMAP login only."""

from dataclasses import dataclass

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
    """`subject`'s EmailAccount (their address, app password, IMAP host,
    port, mailbox and Commsec sender). Raises EmailSyncError (503) when the
    saved password no longer decrypts."""
    who = _Subject(subject)
    values = await settings.effective(who)
    try:
        password = await settings.get_secret("email.app_password", who)
    except SecretDecryptError:
        raise EmailSyncError(503, UNREADABLE_PASSWORD) from None
    return EmailAccount(
        address=str(values["email.address"]).strip(),
        app_password=password or "",
        imap_host=str(values["email.imap_host"]),
        imap_port=int(values["email.imap_port"]),  # type: ignore[arg-type]
        mailbox=str(values["email.mailbox"]),
        commsec_sender=str(values["email.commsec_sender"]),
    )
