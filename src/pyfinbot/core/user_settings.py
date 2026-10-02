"""The settings registry: greentechhub-core's shared user preferences
(theme, timezone, date/number/time formats, rows per page, density,
motion), each person's own, edited at /settings.

Two defaults are PyFinBot's own rather than core's, so pages look as they
always have until someone picks otherwise: 50 rows per page (core: 25) and
"31 Jan 2026" dates (core: ISO). The sidebar preference is left out: PyFinBot
uses the navbar layout, so it would do nothing.
"""

from dataclasses import replace

from greentechhub_core.settings import SettingsRegistry
from greentechhub_core.settings.builtins import (
    DATE_FORMAT,
    PAGE_SIZE,
    SIDEBAR_DEFAULT,
    USER_PREFERENCES,
)

DEFAULT_ROWS_PER_PAGE = 50  # web.paging.PAGE_SIZE (a test keeps them equal)

DEFAULTS = {PAGE_SIZE.key: DEFAULT_ROWS_PER_PAGE, DATE_FORMAT.key: "long"}

USER_SETTINGS = SettingsRegistry(
    replace(s, default=DEFAULTS[s.key]) if s.key in DEFAULTS else s
    for s in USER_PREFERENCES
    if s.key != SIDEBAR_DEFAULT.key
)
