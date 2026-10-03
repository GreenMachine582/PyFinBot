from collections.abc import Iterable
from pathlib import Path

import greentechhub_ui
from fastapi.templating import Jinja2Templates
from greentechhub_fastapi.settings import settings_context
from greentechhub_fastapi.templating import ui_context

def site_banners_context(request) -> dict:
    """The admin-set site banner (Settings › App) as greentechhub-ui's
    site_banners, shown above the navbar on every page. The id is fixed and
    gth_alert_banner remembers a dismissal against the message, so editing
    the text brings it back."""
    values = settings_context(request).get("user_settings") or {}
    message = str(values.get("site.banner") or "").strip()
    if not message:
        return {}
    return {"site_banners": [{"message": message, "tone": values.get("site.banner_tone", "warn"),
                              "id": "site"}]}


# ui_context supplies current_path, so the navbar marks the active page;
# settings_context (register_settings, pyfinbot.py) the signed-in user, the
# user menu, their saved theme, `granted` (so admin-only nav items show) and
# user_settings — which the |date / |money / |number filters and the tables'
# page size follow; site_banners_context the site banner.
templates = Jinja2Templates(directory=Path(__file__).parent / "templates",
                            context_processors=[ui_context, settings_context, site_banners_context])

# greentechhub-ui's template dirs (after ours) plus the shared shell globals
# (brand, nav, vendored asset URLs under the mounts in pyfinbot.py) — see
# greentechhub-ui/docs/contract.md.
greentechhub_ui.install(
    templates.env,
    service_name="PyFinBot",
    nav_items=greentechhub_ui.navigation.build_nav_items(
        custom_items=[
            {"label": "Dashboard", "url": "/", "icon": "speedometer2"},
            {"label": "Stocks", "url": "/stocks", "icon": "graph-up"},
            {"label": "Transactions", "url": "/transactions", "icon": "receipt"},
            {"label": "Import", "url": "/import", "icon": "upload"},
            {"label": "Emails", "url": "/emails", "icon": "envelope"},
            {"label": "Dividends", "url": "/dividends", "icon": "cash-coin"},
            {"label": "Reports", "url": "/reports", "icon": "bar-chart"},
            # Only admins (users.manage) see it: filtered per request on `granted`.
            {"label": "Roles", "url": "/admin/roles", "icon": "shield-lock",
             "required_permission": "users.manage"},
        ],
    ),
)


# money / number / date come from greentechhub_ui.install() above:
# |money → "$1,234.50", |number → full precision with trailing zeros trimmed
# (floats too), |date → "5 Feb 2025". Only the FY label is ours.


def _fy(value: int) -> str:
    """core.fiscal_year's FY N (1 Jul N – 30 Jun N+1) as "N–(N+1)", e.g.
    2024 → "2024–25" — a bare "FY2024" reads as the opposite year to many."""
    return f"{value}–{(value + 1) % 100:02d}"


def _fy_options(fys: Iterable[int]) -> list[tuple[int, str]]:
    """(value, label) pairs for gth_select: 2024 → (2024, "2024–25")."""
    return [(fy, _fy(fy)) for fy in fys]


templates.env.filters["fy"] = _fy
templates.env.filters["fy_options"] = _fy_options
