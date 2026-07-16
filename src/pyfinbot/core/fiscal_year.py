from __future__ import annotations

from datetime import date


def au_fiscal_year(d: date) -> int:
    """AU fiscal year: FY 'N' spans 1 Jul N to 30 Jun N+1 inclusive."""
    return d.year - 1 if d.month <= 6 else d.year
