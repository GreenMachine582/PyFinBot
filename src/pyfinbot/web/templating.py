from decimal import Decimal
from pathlib import Path

import greentechhub_ui
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.loader = ChoiceLoader(
    [
        templates.env.loader,
        FileSystemLoader(greentechhub_ui.templates_path),
        FileSystemLoader(greentechhub_ui.components_path),
    ]
)

# greentechhub-ui shared shell context (brand, nav, every vendored asset URL
# under the /gth-assets and /gth-static mounts in pyfinbot.py) — see
# greentechhub-ui/docs/contract.md.
templates.env.globals.update(greentechhub_ui.shell_globals(
    service_name="PyFinBot",
    nav_items=greentechhub_ui.navigation.build_nav_items(
        custom_items=[
            {"label": "Dashboard", "url": "/", "icon": "speedometer2"},
            {"label": "Stocks", "url": "/stocks", "icon": "graph-up"},
            {"label": "Transactions", "url": "/transactions", "icon": "receipt"},
        ],
    ),
))


def _qty(value) -> str:
    """Units/prices: full stored precision, trailing zeros dropped (never
    scientific notation — Decimal("100").normalize() alone gives 1E+2)."""
    if value is None:
        return ""
    return f"{Decimal(value).normalize():,f}"


def _money(value) -> str:
    return "" if value is None else f"{Decimal(value):,.2f}"


def _fy(value: int) -> str:
    """core.fiscal_year's FY N (1 Jul N – 30 Jun N+1) as "N–(N+1)", e.g.
    2024 → "2024–25" — a bare "FY2024" reads as the opposite year to many."""
    return f"{value}–{(value + 1) % 100:02d}"


templates.env.filters["qty"] = _qty
templates.env.filters["fy"] = _fy
templates.env.filters["money"] = _money
