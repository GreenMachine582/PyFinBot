from pathlib import Path

import greentechhub_ui
from fastapi.templating import Jinja2Templates
from greentechhub_fastapi.templating import ui_context

# ui_context supplies current_path, so the navbar marks the active page.
templates = Jinja2Templates(directory=Path(__file__).parent / "templates", context_processors=[ui_context])

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


templates.env.filters["fy"] = _fy
