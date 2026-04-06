"""Temporal distribution strategy registry for viewpoint building.

Each strategy is a function: dict -> list[dict].
Given a single event, the strategy returns one or more rows
depending on whether the event spans multiple months.

Adding a new strategy means adding a function here with the
@_registry.decorator — no changes to the builder (OCP).
"""

from __future__ import annotations

import logging
import math
import re
from collections.abc import Callable

from datafactory_provenance.registry import Registry

logger = logging.getLogger(__name__)

_registry: Registry[Callable[[dict], list[dict]]] = Registry(
    "distribution strategy"
)
STRATEGIES = _registry.entries

__all__ = ["get_distribution", "even_split", "ceil_split"]

_SUMMARY_DATE_PREC: int = 5  # date_prec value indicating multi-month span
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_date_str(date_str: str) -> str:
    """Validate date string is strictly YYYY-MM-DD.

    Raises:
        ValueError: For non-conforming strings (e.g., ISO datetime,
            slash-separated, missing leading zeros).
    """
    if not _DATE_RE.match(date_str):
        err_msg = (
            f"Expected YYYY-MM-DD date format, got {date_str!r}"
        )
        raise ValueError(err_msg)
    return date_str


def get_distribution(name: str) -> Callable[[dict], list[dict]]:
    """Look up a temporal distribution strategy by name.

    Raises:
        KeyError: If the strategy name is not registered.
    """
    return _registry.get(name)


def _month_first_day(date_str: str) -> str:
    """Extract the first day of the month from a YYYY-MM-DD string.

    Example: "2023-03-15" → "2023-03-01"
    """
    _validate_date_str(date_str)
    parts = date_str.split("-")
    return f"{parts[0]}-{parts[1]}-01"


def _months_between(start_str: str, end_str: str) -> list[str]:
    """Generate first-of-month strings between two dates (inclusive).

    Example: "2023-01-15" to "2023-03-31" → ["2023-01-01",
    "2023-02-01", "2023-03-01"]
    """
    _validate_date_str(start_str)
    _validate_date_str(end_str)
    start_parts = start_str.split("-")
    end_parts = end_str.split("-")

    start_year = int(start_parts[0])
    start_month = int(start_parts[1])
    end_year = int(end_parts[0])
    end_month = int(end_parts[1])

    months: list[str] = []
    year, month = start_year, start_month
    while (year, month) <= (end_year, end_month):
        months.append(f"{year}-{month:02d}-01")
        month += 1
        if month > 12:
            month = 1
            year += 1

    return months


@_registry.decorator("even_split")
def even_split(event: dict) -> list[dict]:
    """Distribute summary events evenly across spanned months.

    For date_prec=5 events: divides best/low/high evenly across
    months from date_start to date_end (inclusive). Each output
    row gets a date_month field.

    For all other events: returns a single row with date_month
    derived from date_end (matching production GedLoader behavior).
    """
    date_prec = event.get("date_prec")
    date_end = event.get("date_end") or event.get("date_start")

    if date_prec != _SUMMARY_DATE_PREC:
        # Non-summary: single row, month from date_end
        row = {**event, "date_month": _month_first_day(str(date_end))}
        return [row]

    # Summary event: distribute across months
    date_start = event.get("date_start")
    if not date_start or not date_end:
        err_msg = (
            f"Summary event (date_prec=5) missing date_start or "
            f"date_end: id={event.get('id')}"
        )
        logger.error(err_msg)
        raise ValueError(err_msg)

    months = _months_between(date_start, date_end)
    if not months:
        err_msg = (
            f"Summary event spans zero months: "
            f"date_start={date_start}, date_end={date_end}"
        )
        logger.error(err_msg)
        raise ValueError(err_msg)

    n_months = len(months)
    best = (event.get("best") or 0) / n_months
    low = (event.get("low") or 0) / n_months
    high = (event.get("high") or 0) / n_months

    rows: list[dict] = []
    for month_str in months:
        row = {
            **event,
            "best": best,
            "low": low,
            "high": high,
            "date_month": month_str,
        }
        rows.append(row)

    return rows


@_registry.decorator("ceil_split")
def ceil_split(event: dict) -> list[dict]:
    """Production-parity summary event distribution.

    Matches the production GedLoader's fix_summary_events logic:

    Detection: event is summary if best > 0, spans > 1 month,
    AND best >= span (enough fatalities for at least 1 per month).
    This differs from even_split which uses date_prec == 5.

    Distribution: ceil(fatalities / span) — rounds up to ensure
    every month gets at least 1 fatality. This may inflate totals
    (e.g., best=7 over 3 months → 3+3+3=9, not 7).

    Non-summary events get date_month from date_end.
    """
    date_end = event.get("date_end") or event.get("date_start")
    date_start = event.get("date_start")
    best = event.get("best") or 0

    # Compute month span for detection
    if date_start and date_end:
        months = _months_between(date_start, date_end)
        summary_period = len(months)
    else:
        summary_period = 1
        months = []

    # Production detection: best>0 AND span>1 AND best>=span
    is_summary = (
        best > 0
        and summary_period > 1
        and best >= summary_period
    )

    if not is_summary:
        # Non-summary: single row, month from date_end
        row = {**event, "date_month": _month_first_day(str(date_end))}
        return [row]

    # Summary event: distribute with ceil
    if not months:
        err_msg = (
            f"Summary event has no month span: "
            f"date_start={date_start}, date_end={date_end}"
        )
        logger.error(err_msg)
        raise ValueError(err_msg)

    ceil_best = int(math.ceil(best / summary_period))
    low = event.get("low") or 0
    high = event.get("high") or 0
    ceil_low = int(math.ceil(low / summary_period))
    ceil_high = int(math.ceil(high / summary_period))

    rows: list[dict] = []
    for month_str in months:
        row = {
            **event,
            "best": ceil_best,
            "low": ceil_low,
            "high": ceil_high,
            "date_month": month_str,
        }
        rows.append(row)

    return rows
