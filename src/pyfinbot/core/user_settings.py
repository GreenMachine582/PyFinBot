"""The settings registry: greentechhub-core's shared user preferences
(theme, timezone, date/number/time formats, rows per page, density,
motion), each person's own, edited at /settings.

Two defaults are PyFinBot's own rather than core's, so pages look as they
always have until someone picks otherwise: 50 rows per page (core: 25) and
"31 Jan 2026" dates (core: ISO). The sidebar preference is left out: PyFinBot
uses the navbar layout, so it would do nothing.

Plus PyFinBot's own "Email sync" group: the user's mailbox for Commsec sync,
its app password a write-only, encrypted secret setting.
"""

from dataclasses import replace

from greentechhub_core.settings import Setting, SettingScope, SettingsRegistry, SettingType
from .permissions import SETTINGS_MANAGE
from greentechhub_core.settings.builtins import (
    DATE_FORMAT,
    PAGE_SIZE,
    SIDEBAR_DEFAULT,
    USER_PREFERENCES,
)

DEFAULT_ROWS_PER_PAGE = 50  # web.paging.PAGE_SIZE (a test keeps them equal)

DEFAULTS = {PAGE_SIZE.key: DEFAULT_ROWS_PER_PAGE, DATE_FORMAT.key: "long"}

EMAIL_GROUP = "Email sync"

# Each user's own mailbox for Commsec email sync (core/email_accounts.py).
# The app password is a secret: encrypted in gth_settings (the cipher is
# register_settings' FernetCipher), write-only on /settings, and only ever
# read back for the IMAP login.
EMAIL_SETTINGS = (
    Setting(key="email.address", type=SettingType.STR, default="", scope=SettingScope.USER,
            label="Email address", group=EMAIL_GROUP,
            help_text="The mailbox Commsec sends your trade confirmations to."),
    Setting(key="email.app_password", type=SettingType.STR, default="", scope=SettingScope.USER,
            label="App password", group=EMAIL_GROUP, secret=True,
            help_text="A Google App Password (not your account password). Stored encrypted; "
                      "it's never shown again."),
    Setting(key="email.imap_host", type=SettingType.STR, default="imap.gmail.com",
            scope=SettingScope.USER, label="IMAP server", group=EMAIL_GROUP),
    Setting(key="email.imap_port", type=SettingType.INT, default=993, scope=SettingScope.USER,
            label="IMAP port", group=EMAIL_GROUP, min=1, max=65535),
    Setting(key="email.mailbox", type=SettingType.STR, default="INBOX", scope=SettingScope.USER,
            label="Mailbox", group=EMAIL_GROUP, help_text="The folder or label to read."),
    Setting(key="email.commsec_sender", type=SettingType.STR, default="bounceback@commsec.com.au",
            scope=SettingScope.USER, label="Commsec sender", group=EMAIL_GROUP,
            help_text="Only emails from this address are imported."),
)

SITE_GROUP = "Site"

# App-wide settings, on /settings › App for admins (settings.manage).
SITE_SETTINGS = (
    Setting(key="site.banner", type=SettingType.STR, default="", scope=SettingScope.APP,
            label="Site banner", group=SITE_GROUP, edit_permission=SETTINGS_MANAGE,
            help_text="Shown to everyone above the navbar, e.g. planned maintenance. "
                      "Leave empty for none."),
    Setting(key="site.banner_tone", type=SettingType.CHOICE, default="warn", scope=SettingScope.APP,
            label="Banner style", group=SITE_GROUP, edit_permission=SETTINGS_MANAGE,
            choices={"info": "Info", "warn": "Warning", "bad": "Alert"}),
)

USER_SETTINGS = SettingsRegistry([
    *(replace(s, default=DEFAULTS[s.key]) if s.key in DEFAULTS else s
      for s in USER_PREFERENCES
      if s.key != SIDEBAR_DEFAULT.key),
    *EMAIL_SETTINGS,
    *SITE_SETTINGS,
])
