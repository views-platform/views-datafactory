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
import warnings
from collections.abc import Callable

from datafactory_provenance.registry import Registry
from datafactory_viewpoint.apportionment import apportion

logger = logging.getLogger(__name__)

_registry: Registry[Callable[[dict], list[dict]]] = Registry(
    "distribution strategy"
)

__all__ = [
    "get_distribution",
    "date_end_only",
    "uniform_span",
    "even_split",
    "ceil_split",
    "floor_split",
    "source_aware",
]

_SUMMARY_DATE_PREC: int = 5  # date_prec value indicating multi-month span

#: ``date_prec`` at or above which UCDP has declared it does not know the
#: month. 4 is "month known, day unknown"; combined with a span crossing a
#: month boundary that makes the month itself ambiguous, so 4 is included.
#: This is the *declared* trigger -- contrast ``ceil_split``, which infers
#: a summary event from span and magnitude without consulting
#: ``date_prec`` at all. See section 4 of
#: ``reports/2026-11-04_summary_event_allocation_dossier/11_allocator_spec.md``.
_KTI_DATE_PREC: int = 4

#: Fields that carry the extensive count and must be conserved
#: independently (ADR-040; ADR-049 section 5 does the same spatially).
_EXTENSIVE_FIELDS: tuple[str, ...] = ("best", "low", "high")
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


@_registry.decorator("date_end_only")
def date_end_only(event: dict) -> list[dict]:
    """Assign all events to their date_end month. No distribution.

    Matches VIEWSER GedLoader behavior when fix_summary_events
    is not enabled. Every event produces exactly one output row
    with date_month derived from date_end, regardless of whether
    the event spans multiple months.
    """
    date_end = event.get("date_end") or event.get("date_start")
    return [{**event, "date_month": _month_first_day(str(date_end))}]


@_registry.decorator("uniform_span")
def uniform_span(event: dict) -> list[dict]:
    """Spread a temporally imprecise event evenly over the months it spans.

    **The declared-trigger, conserving temporal allocator** -- option T1 in
    the allocator spec, and the floor that any weighted temporal strategy
    has to beat before its extra assumption is earned.

    Triggers on UCDP's own declaration: ``date_prec >= 4`` (the source does
    not know the month) **and** a span crossing a month boundary. Both
    conditions are needed. ``date_prec >= 4`` with a single-month span needs
    no allocation -- the month is already right -- and a span over more than
    one month with ``date_prec <= 3`` is a *precisely dated* event that
    straddles a calendar boundary, which is a different problem with a
    different answer.

    Conservation is exact, on ``best``, ``low`` and ``high`` independently,
    because allocation goes through
    :func:`datafactory_viewpoint.apportionment.apportion`. Two consequences
    worth stating:

    - **It cannot inflate.** ``ceil_split`` assigns ``ceil(v/m)`` to every
      month, so it sums to at least ``v`` and in practice above it; the
      measured excess across the store is 0.91%. Largest-remainder
      apportionment makes that impossible.
    - **One death over three months stays one death**, landing in a single
      month rather than becoming three. Rows are emitted only where the
      allocation is nonzero, so output size is bounded by
      ``min(v, span)`` rather than by ``span``.

    Non-triggering events get one row at their ``date_end`` month, which is
    ``date_end_only``'s behaviour.
    """
    date_end = event.get("date_end") or event.get("date_start")
    date_start = event.get("date_start") or date_end
    single = [{**event, "date_month": _month_first_day(str(date_end))}]

    if int(event.get("date_prec") or 0) < _KTI_DATE_PREC:
        return single

    months = _months_between(str(date_start), str(date_end))
    if len(months) <= 1:
        return single

    weights = dict.fromkeys(months, 1.0)
    allocations = {
        field: apportion(int(event.get(field) or 0), weights)
        for field in _EXTENSIVE_FIELDS
    }

    rows = [
        {
            **event,
            "date_month": month,
            **{f: allocations[f][month] for f in _EXTENSIVE_FIELDS},
            "_temporal_distributed": True,
            "_temporal_n_months": len(months),
        }
        for month in months
        if any(allocations[f][month] > 0 for f in _EXTENSIVE_FIELDS)
    ]

    # A zero-valued event still happened; keep it at its date_end month
    # rather than dropping it, so counts stay accountable (ADR-040).
    return rows or single


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


def _split_summary(
    event: dict,
    rounding_fn: Callable[[float], float],
) -> list[dict]:
    """Shared detection + distribution for summary events.

    Detection (ADR-023 invariant): event is summary if best > 0,
    spans > 1 month, AND best >= span. Non-summary events produce
    a single row with date_month from date_end.

    Summary events are expanded to one row per spanned month, with
    fatalities divided by the rounding function (ceil or floor).
    """
    date_end = event.get("date_end") or event.get("date_start")
    date_start = event.get("date_start")
    best = event.get("best") or 0

    if date_start and date_end:
        months = _months_between(date_start, date_end)
        summary_period = len(months)
    else:
        summary_period = 1
        months = []

    is_summary = (
        best > 0
        and summary_period > 1
        and best >= summary_period
    )

    if not is_summary:
        row = {
            **event,
            "date_month": _month_first_day(str(date_end)),
        }
        return [row]

    if not months:
        err_msg = (
            f"Summary event has no month span: "
            f"date_start={date_start}, date_end={date_end}"
        )
        logger.error(err_msg)
        raise ValueError(err_msg)

    low = event.get("low") or 0
    high = event.get("high") or 0
    r_best = int(rounding_fn(best / summary_period))
    r_low = int(rounding_fn(low / summary_period))
    r_high = int(rounding_fn(high / summary_period))

    rows: list[dict] = []
    for month_str in months:
        row = {
            **event,
            "best": r_best,
            "low": r_low,
            "high": r_high,
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
    return _split_summary(event, math.ceil)


@_registry.decorator("floor_split")
def floor_split(event: dict) -> list[dict]:
    """Summary event distribution with floor rounding.

    Same detection logic as ceil_split but uses
    floor(fatalities / span). Matches older VIEWSER .9 loader
    versions (pre-v25.9.11).

    Non-summary events get date_month from date_end.
    """
    return _split_summary(event, math.floor)


@_registry.decorator("source_aware")
def source_aware(event: dict) -> list[dict]:
    """Source-type-aware distribution matching VIEWSER behavior.

    .. deprecated::
        Use ``source_distribution_map={"annual": "date_end_only"}``
        with ``distribution_strategy="ceil_split"`` in
        ViewpointConfig instead.

    VIEWSER loads data sources sequentially with different settings:
    - Annual loader: fix_summary_events=False → date_end_only
    - .9 / candidate loader: fix_summary_events=True → ceil_split

    This composite strategy reads _source_type from the event and
    delegates to the appropriate strategy.
    """
    warnings.warn(
        "source_aware strategy is deprecated; use "
        "source_distribution_map={'annual': 'date_end_only'} "
        "with distribution_strategy='ceil_split' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    source_type = event.get("_source_type", "")
    if source_type == "annual":
        return date_end_only(event)
    return ceil_split(event)
