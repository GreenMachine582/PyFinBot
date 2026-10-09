"""The reports from the shell, as CSV or JSON — the same core/reports.py
functions and row layout (core/report_rows.py) as the web's Reports page and
its CSV downloads, so the CLI and the web never disagree. Run from the
project root:

    python scripts/cli.py holdings  --user alice [--as-of 2025-06-30]
    python scripts/cli.py gains     --user alice [--fy 2024]
    python scripts/cli.py dividends --user alice [--fy 2024]

Each takes --format csv|json (default csv) and -o/--output FILE (default
stdout). A CSV file starts with a UTF-8 BOM, like the web's downloads, so
Excel reads it as UTF-8. Read-only: it never migrates or writes the database.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import io
import sys
from datetime import date
from typing import Optional, Sequence, TextIO

from greentechhub_core.dates import fiscal_year
from greentechhub_fastapi.downloads import BOM
from sqlmodel.ext.asyncio.session import AsyncSession

from .core import report_rows, reports
from .models.user_models import User
from .schemas.report_schemas import CapitalGainsReport, DividendsReport, HoldingsReport


Report = HoldingsReport | CapitalGainsReport | DividendsReport


class UnknownUser(LookupError):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pyfinbot", description="Export a PyFinBot report as CSV or JSON.")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--user", required=True, help="the user id whose transactions to report on")
    common.add_argument("--format", choices=("csv", "json"), default="csv", help="output format (default: csv)")
    common.add_argument("-o", "--output", help="write to this file instead of stdout")

    commands = parser.add_subparsers(dest="report", required=True, metavar="REPORT")
    holdings = commands.add_parser("holdings", parents=[common], help="units held per stock on a date")
    holdings.add_argument("--as-of", type=date.fromisoformat, default=None,
                          help="snapshot date, YYYY-MM-DD (default: today)")
    gains = commands.add_parser("gains", parents=[common], help="realised capital gains for a financial year")
    gains.add_argument("--fy", type=int, default=None,
                       help="financial year by its starting year, e.g. 2024 for 2024–25 (default: the current one)")
    dividends = commands.add_parser("dividends", parents=[common], help="dividend income")
    dividends.add_argument("--fy", type=int, default=None,
                           help="financial year by its starting year (default: all time)")
    return parser


async def build_report(session: AsyncSession, args: argparse.Namespace) -> Report:
    """The report `args` asks for. Raises UnknownUser for a user id that
    doesn't exist, rather than printing an empty report."""
    if await session.get(User, args.user) is None:
        raise UnknownUser(f"no user {args.user!r}")
    if args.report == "holdings":
        return await reports.holdings_report(session, args.user, args.as_of or date.today())
    if args.report == "gains":
        fy = args.fy if args.fy is not None else fiscal_year(date.today())
        return await reports.capital_gains_report(session, args.user, fy)
    return await reports.dividends_report(session, args.user, args.fy)


def render(report: Report, fmt: str) -> str:
    """`report` as JSON (the API's shape) or CSV (the web download's columns)."""
    if fmt == "json":
        return report.model_dump_json(indent=2) + "\n"
    if isinstance(report, HoldingsReport):
        rows = report_rows.holdings_rows(report)
    elif isinstance(report, CapitalGainsReport):
        rows = report_rows.gains_rows(report)
    else:
        rows = report_rows.dividends_rows(report)
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return buf.getvalue()


async def run(argv: Optional[Sequence[str]] = None, stdout: Optional[TextIO] = None,
              stderr: Optional[TextIO] = None) -> int:
    args = build_parser().parse_args(argv)
    from .db.session import get_session_factory

    async with get_session_factory()() as session:
        try:
            report = await build_report(session, args)
        except UnknownUser as exc:
            print(f"Nothing exported: {exc}.", file=stderr or sys.stderr)
            return 1
    text = render(report, args.format)
    if args.output:
        # newline="": the csv module already wrote \r\n line endings.
        with open(args.output, "w", encoding="utf-8", newline="") as f:
            f.write((BOM if args.format == "csv" else "") + text)
    else:
        (stdout or sys.stdout).write(text)
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:  # pragma: no cover - asyncio.run around run()
    return asyncio.run(run(argv))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
