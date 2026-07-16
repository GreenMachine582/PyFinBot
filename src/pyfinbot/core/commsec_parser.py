"""
Parses Commsec "bought"/"sold" trade confirmation emails into a structured
trade record.

Built and verified against two real Commsec confirmation emails (one buy,
one sell) for ordinary ASX shares. Other Commsec email types this parser has
NOT seen — partial fills, DRP (dividend reinvestment), managed funds,
off-market transfers, corporate actions — will likely fail to match and
raise CommsecParseError rather than being silently mis-parsed.

There is no contract-note/reference number in this email format, so nothing
is parsed for one. There is also no explicit "trade date" field — the
caller passes the email's own Date header (`received_at`) as a stand-in,
since Commsec sends these confirmations promptly after the trade. Brokerage
is not stated as a separate figure either; it's derived from the difference
between the total settlement amount (which includes brokerage) and the
gross trade value (units x price, which explicitly excludes brokerage).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


class CommsecParseError(ValueError):
    pass


@dataclass
class ParsedCommsecTrade:
    action: str  # "BOUGHT" or "SOLD"
    symbol: str
    company_name: str
    units: Decimal
    price_per_unit: Decimal  # excludes brokerage
    brokerage: Decimal       # derived: |total_settlement - units*price|
    total_settlement: Decimal
    trade_date: date         # from the email's Date header, not a body field
    settlement_date: date
    trading_account: str


_SUBJECT_RE = re.compile(
    r"CommSec\s*-\s*(Bought|Sold)\s+([\d,]+)\s+units?\s+of\s+([A-Z]{1,6})",
    re.IGNORECASE,
)
_BODY_TRADE_RE = re.compile(
    r"You've (bought|sold) ([\d,]+) units? in (.+?) \(([A-Z]{1,6})\) at a price of "
    r"\$([\d,]+\.\d+) per unit \(not including brokerage\), on trading account (\S.*?)\.",
    re.IGNORECASE,
)
_SETTLEMENT_RE = re.compile(
    r"total settlement amount, including brokerage, is \$([\d,]+\.\d+).*?"
    r"on (\d{1,2} [A-Za-z]{3} \d{4})",
    re.IGNORECASE | re.DOTALL,
)


def _parse_amount(s: str) -> Decimal:
    return Decimal(s.replace(",", ""))


def _parse_settlement_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%d %b %Y").date()


def parse_commsec_email(subject: str, body: str, received_at: datetime) -> ParsedCommsecTrade:
    subject_match = _SUBJECT_RE.search(subject)
    if not subject_match:
        raise CommsecParseError("Subject does not match a Commsec bought/sold confirmation")
    subj_action, subj_units_str, subj_symbol = subject_match.groups()

    body_match = _BODY_TRADE_RE.search(body)
    if not body_match:
        raise CommsecParseError("Could not find a \"You've bought/sold ... units in ...\" line in the body")
    action, units_str, company_name, symbol, price_str, trading_account = body_match.groups()

    action_norm = action.upper()
    symbol_norm = symbol.upper()
    units = _parse_amount(units_str)

    # Cross-check subject vs. body rather than trusting either alone.
    if subj_action.upper() != action_norm:
        raise CommsecParseError(f"Subject action '{subj_action}' does not match body action '{action}'")
    if subj_symbol.upper() != symbol_norm:
        raise CommsecParseError(f"Subject symbol '{subj_symbol}' does not match body symbol '{symbol}'")
    if _parse_amount(subj_units_str) != units:
        raise CommsecParseError(f"Subject units '{subj_units_str}' does not match body units '{units_str}'")

    price_per_unit = _parse_amount(price_str)

    settlement_match = _SETTLEMENT_RE.search(body)
    if not settlement_match:
        raise CommsecParseError("Could not find the total settlement amount / settlement date in the body")
    total_settlement = _parse_amount(settlement_match.group(1))
    settlement_date = _parse_settlement_date(settlement_match.group(2))

    gross = units * price_per_unit
    brokerage = (total_settlement - gross) if action_norm == "BOUGHT" else (gross - total_settlement)

    tolerance = Decimal("0.01")
    if brokerage < -tolerance:
        raise CommsecParseError(
            f"Derived brokerage is negative ({brokerage}) — total_settlement/units/price likely mis-parsed"
        )
    brokerage = max(brokerage, Decimal("0"))

    return ParsedCommsecTrade(
        action=action_norm,
        symbol=symbol_norm,
        company_name=company_name.strip(),
        units=units,
        price_per_unit=price_per_unit,
        brokerage=brokerage,
        total_settlement=total_settlement,
        trade_date=received_at.date(),
        settlement_date=settlement_date,
        trading_account=trading_account.strip(),
    )
