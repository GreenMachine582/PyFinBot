"""The settings registry: greentechhub-core's shared user preferences
(theme, timezone, date/number/time formats, rows per page, density,
motion), each person's own, edited at /settings.

Two defaults are PyFinBot's own rather than core's, so pages look as they
always have until someone picks otherwise: 50 rows per page (core: 25) and
"31 Jan 2026" dates (core: ISO). The sidebar preference is left out: PyFinBot
uses the navbar layout, so it would do nothing.

Plus PyFinBot's own "Email sync" group: the user's mailbox for Commsec sync,
its app password a write-only, encrypted secret setting. And core's site
banner (Settings › App, for settings.manage), which greentechhub-fastapi's
settings_context shows above the navbar on every page.

Email out: core's smtp_settings (Settings › App › Outgoing email, for
settings.manage; the password a secret) is the mail server register_email
sends through, and core's notification_preferences gives each user a
"Syncs and imports" choice of in-app, email, both or off for the notices
core/audit_events.py leaves (email only reaches a confirmed address).
"""

from dataclasses import replace

from greentechhub_core.email import imap_settings, smtp_settings
from greentechhub_core.notifications import notification_preferences
from greentechhub_core.settings import Setting, SettingScope, SettingsRegistry, SettingType
from .audit_events import NOTICE_CATEGORY
from .email_sync import COMMSEC_SENDER
from .permissions import SETTINGS_MANAGE
from greentechhub_core.settings.builtins import (
    DATE_FORMAT,
    PAGE_SIZE,
    SIDEBAR_DEFAULT,
    USER_PREFERENCES,
    site_banner_settings,
)

DEFAULT_ROWS_PER_PAGE = 50  # also the web tables' page_size (TableState)
PAGE_SIZES = (10, 25, DEFAULT_ROWS_PER_PAGE)  # the tables' rows-per-page choices

DEFAULTS = {PAGE_SIZE.key: DEFAULT_ROWS_PER_PAGE, DATE_FORMAT.key: "long"}

EMAIL_GROUP = "Email sync"

# Each user's own mailbox for Commsec email sync (core/email_accounts.py):
# core's imap_settings, with PyFinBot's wording, plus the Commsec sender.
# The app password is a secret: encrypted in gth_settings (the cipher is
# register_settings' FernetCipher), write-only on /settings, and only ever
# read back for the IMAP login.
_HELP_TEXT = {
    "email.address": "The mailbox Commsec sends your trade confirmations to.",
    "email.app_password": "A Google App Password (not your account password). Stored encrypted; "
                          "it's never shown again.",
}

EMAIL_SETTINGS = (
    *(replace(s, help_text=_HELP_TEXT.get(s.key, s.help_text)) for s in imap_settings(group=EMAIL_GROUP)),
    Setting(key="email.commsec_sender", type=SettingType.STR, default=COMMSEC_SENDER,
            scope=SettingScope.USER, label="Commsec sender", group=EMAIL_GROUP,
            help_text="Only emails from this address are imported."),
)

USER_SETTINGS = SettingsRegistry([
    *(replace(s, default=DEFAULTS[s.key]) if s.key in DEFAULTS else s
      for s in USER_PREFERENCES
      if s.key != SIDEBAR_DEFAULT.key),
    *EMAIL_SETTINGS,
    *notification_preferences({NOTICE_CATEGORY: "Syncs and imports"}),
    *smtp_settings(edit_permission=SETTINGS_MANAGE, group="Outgoing email"),
    *site_banner_settings(edit_permission=SETTINGS_MANAGE),
])
