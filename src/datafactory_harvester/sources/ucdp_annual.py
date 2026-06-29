"""UCDP/GED Annual dataset source.

Fetches georeferenced event data from the Uppsala Conflict Data Program.
API docs: https://ucdp.uu.se/apidocs/

Source-specific concerns: API URL, schema definition, pagination,
token handling, version string. Uses the shared harvester skeleton
(validation, storage, provenance) from the parent package.
"""

from __future__ import annotations

import datetime
import logging
import os
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import requests

from datafactory_harvester.event_validation import (
    ComparisonResult,
    compare_snapshots,
    date_range,
    validate_dgp_assumptions,
    validate_events,
)
from datafactory_harvester.snapshot_storage import archive_snapshot, save_event_snapshot
from datafactory_harvester.sources import register_source
from datafactory_harvester.sources._ucdp_common import (
    UCDP_GED_API_BASE,
    validate_envelope,
)
from datafactory_harvester.validation import (
    validate_nonempty_string,
    validate_positive_float,
    validate_positive_int,
    validate_year_range,
)
from datafactory_http import request_with_retry
from datafactory_provenance import (
    DIGEST_SCHEME,
    LEDGER_VERSION,
    append_ledger_entry,
    last_digest,
)

logger = logging.getLogger(__name__)

DATASET_ID = "ucdp_annual"
_LOG_EVERY_N_PAGES: int = 50
_FETCH_DURATION_PRECISION: int = 1  # Decimal places for fetch_duration_s in ledger
_RATE_LIMIT_MAX_RETRIES: int = 5
_YEAR_OFFSET: int = 1999  # v25.1 covers through 2024 → major + 1999
_RATE_LIMIT_BASE_DELAY: float = 30.0  # seconds; UCDP rate window is ~1 minute
_TOTALCOUNT_ABS_TOLERANCE: int = 1100
_TOTALCOUNT_PCT_TOLERANCE: float = 0.01

# ---- UCDP-specific schema definition ----

REQUIRED_FIELDS: set[str] = {
    "id",
    "country_id",
    "country",
    "date_start",
    "best",
    "high",
    "low",
    "type_of_violence",
    "event_clarity",
    "code_status",
    "where_prec",
    "date_prec",
    "number_of_sources",
}

FIELD_TYPES: dict[str, tuple[type, ...]] = {
    "id": (int,),
    "country_id": (int,),
    "country": (str,),
    "date_start": (str,),
    "best": (int, float),
    "high": (int, float),
    "low": (int, float),
    "type_of_violence": (int,),
    "event_clarity": (int, float),
    "where_prec": (int,),
    "date_prec": (int,),
    "number_of_sources": (int,),
}

# ---- DGP assumption checks (C-257) ----

_VALID_DATE_PREC = {1, 2, 3, 4, 5}
_VALID_VIOLENCE_TYPE = {1, 2, 3}


def _check_date_prec_range(event: dict) -> str | None:
    """date_prec must be in {1,2,3,4,5}."""
    val = event.get("date_prec")
    if val is not None and val not in _VALID_DATE_PREC:
        return f"date_prec={val} outside {_VALID_DATE_PREC}"
    return None


def _check_violence_type(event: dict) -> str | None:
    """type_of_violence must be in {1,2,3}."""
    val = event.get("type_of_violence")
    if val is not None and val not in _VALID_VIOLENCE_TYPE:
        return f"type_of_violence={val} outside {_VALID_VIOLENCE_TYPE}"
    return None


def _check_coordinate_bounds(event: dict) -> str | None:
    """Latitude in [-90,90], longitude in [-180,180]."""
    for field, lo, hi in (
        ("latitude", -90, 90),
        ("longitude", -180, 180),
    ):
        val = event.get(field)
        if val is not None:
            try:
                fval = float(val)
                if not (lo <= fval <= hi):
                    return f"{field}={fval} outside [{lo},{hi}]"
            except (TypeError, ValueError):
                pass
    return None


def _check_best_high_low_ordering(event: dict) -> str | None:
    """low <= best <= high."""
    low = event.get("low")
    best = event.get("best")
    high = event.get("high")
    if (
        low is not None
        and best is not None
        and isinstance(low, (int, float))
        and isinstance(best, (int, float))
        and low > best
    ):
        return f"low ({low}) > best ({best})"
    if (
        best is not None
        and high is not None
        and isinstance(best, (int, float))
        and isinstance(high, (int, float))
        and best > high
    ):
        return f"best ({best}) > high ({high})"
    return None


def _check_coords_non_null(event: dict) -> str | None:
    """Latitude and longitude must not be None."""
    if event.get("latitude") is None:
        return "latitude is None"
    if event.get("longitude") is None:
        return "longitude is None"
    return None


UCDP_DGP_CHECKS: tuple[
    Callable[[dict], str | None], ...
] = (
    _check_date_prec_range,
    _check_violence_type,
    _check_coordinate_bounds,
    _check_best_high_low_ordering,
    _check_coords_non_null,
)


# ---- Config ----


@dataclass(frozen=True)
class UcdpAnnualConfig:
    """Configuration for fetching UCDP/GED Annual data.

    Separates harvesting concerns from reporting concerns (SRP).
    No ranking_months, escalation_months, or top_n_countries here.
    """

    # Dataset identity — sentinels resolved in __post_init__
    version: str = ""
    start_year: int = 1989
    end_year: int = 0

    # API transport
    base_url: str = UCDP_GED_API_BASE
    page_size: int = 1000
    timeout: int = 30  # paginated JSON ~100 KB/page (ADR-018)
    max_retries: int = 3
    page_delay: float = 2.0  # seconds between paginated requests

    # Storage
    data_dir: Path = Path("data/raw/ucdp_annual")
    ledger_path: Path = Path("provenance/ucdp_annual/ingestion_ledger.jsonl")

    def __post_init__(self) -> None:
        if not self.version:
            major = datetime.datetime.now(tz=datetime.UTC).year - 2001
            object.__setattr__(self, "version", f"{major}.1")
        if self.end_year == 0:
            major = int(self.version.split(".")[0])
            object.__setattr__(self, "end_year", major + _YEAR_OFFSET)
        validate_year_range(self.start_year, self.end_year)
        validate_positive_int(self.page_size, "page_size")
        validate_positive_int(self.max_retries, "max_retries")
        validate_positive_float(self.page_delay, "page_delay")
        validate_positive_int(self.timeout, "timeout")
        validate_nonempty_string(self.version, "version")


# ---- API client ----


def get_ucdp_token(token: str | None = None) -> str:
    """Resolve API token from argument or environment."""
    resolved = token or os.environ.get("UCDP_API_TOKEN")
    if not resolved:
        err_msg = (
            "UCDP API token required. Set UCDP_API_TOKEN environment "
            "variable or pass token= to fetch_ucdp_annual()."
        )
        logger.error(err_msg)
        raise ValueError(err_msg)
    return resolved


def fetch_paginated(
    config: UcdpAnnualConfig,
    token: str | None = None,
    *,
    max_pages: int | None = None,
) -> list[dict]:
    """Fetch all UCDP/GED Annual events with pagination.

    Args:
        config: Harvest configuration.
        token: API token (falls back to UCDP_API_TOKEN env var).
        max_pages: Stop after this many pages (None = fetch all).

    Returns:
        List of raw event dicts.
    """
    api_token = get_ucdp_token(token)
    url = f"{config.base_url}/{config.version}"
    headers = {"x-ucdp-access-token": api_token}
    params: dict = {
        "StartDate": f"{config.start_year}-01-01",
        "EndDate": f"{config.end_year}-12-31",
        "pagesize": config.page_size,
    }

    all_events: list[dict] = []
    page = 1
    total_pages = None

    while True:
        params["page"] = page

        # The UCDP API rate-limits after ~40 requests with HTTP 400.
        # request_with_retry correctly fails fast on 4xx (non-retryable
        # in general), but rate limiting IS retryable — just not
        # immediately. Catch 400s here and back off before retrying
        # the same page.
        for rate_attempt in range(_RATE_LIMIT_MAX_RETRIES):
            try:
                response = request_with_retry(
                    url,
                    headers=headers,
                    params=params,
                    max_retries=config.max_retries,
                    timeout=config.timeout,
                )
                break
            except requests.HTTPError as exc:
                if (
                    exc.response is not None
                    and exc.response.status_code == 400
                    and rate_attempt < _RATE_LIMIT_MAX_RETRIES - 1
                ):
                    delay = (
                        _RATE_LIMIT_BASE_DELAY * (2 ** rate_attempt)
                        + random.uniform(0, 5)
                    )
                    logger.warning(
                        "Rate limited at page %d (attempt %d/%d), "
                        "backing off %.0fs",
                        page,
                        rate_attempt + 1,
                        _RATE_LIMIT_MAX_RETRIES,
                        delay,
                    )
                    time.sleep(delay)
                else:
                    raise

        data = response.json()

        if page == 1:
            validate_envelope(data)

        if total_pages is None:
            total_pages = data.get("TotalPages", 1)
            total_count = data.get("TotalCount", 0)
            logger.info(
                "UCDP GED %s: %d events across %d pages (%d-%d)",
                config.version,
                total_count,
                total_pages,
                config.start_year,
                config.end_year,
            )

        results = data.get("Result", [])
        if not results:
            break

        all_events.extend(results)
        if page % _LOG_EVERY_N_PAGES == 0 or page == 1:
            logger.info(
                "Page %d/%d (%d events so far)",
                page,
                total_pages,
                len(all_events),
            )

        if page >= total_pages:
            break
        if max_pages is not None and page >= max_pages:
            logger.info("Stopped after %d pages (max_pages limit)", max_pages)
            break
        time.sleep(config.page_delay)
        page += 1

    logger.info("Fetched %d total events", len(all_events))

    # Assert fetched count against API's TotalCount. The UCDP API
    # includes type_of_violence=4 events in TotalCount but excludes
    # them from Result — a consistent offset of ~1000 events across
    # all versions (annual and candidate). For annual (384K events)
    # this is 0.26%; for small candidate versions (200–2300 events)
    # it can be 40–100%. Use both absolute and percentage thresholds:
    # only raise if shortfall exceeds BOTH 1% AND 1100 events.
    if max_pages is None and total_count and total_count > 0:
        shortfall = total_count - len(all_events)
        shortfall_pct = shortfall / total_count
        exceeds_pct = shortfall_pct > _TOTALCOUNT_PCT_TOLERANCE
        exceeds_abs = shortfall > _TOTALCOUNT_ABS_TOLERANCE
        if exceeds_pct and exceeds_abs:
            err_msg = (
                f"Fetch count mismatch: API reports {total_count} "
                f"events but only {len(all_events)} fetched "
                f"({shortfall_pct:.1%} shortfall, {shortfall} events). "
                f"Exceeds both {_TOTALCOUNT_PCT_TOLERANCE:.0%} and "
                f"{_TOTALCOUNT_ABS_TOLERANCE} absolute tolerance."
            )
            logger.error(err_msg)
            raise ValueError(err_msg)
        if shortfall > 0:
            logger.info(
                "TotalCount=%d, fetched=%d (shortfall=%d, %.2f%% "
                "— within tolerance, likely type_of_violence=4 "
                "filtering)",
                total_count,
                len(all_events),
                shortfall,
                shortfall_pct * 100,
            )

    return all_events


# ---- Version Discovery ----

_ANNUAL_DISCOVERY_MAX_PROBES: int = 3
_ANNUAL_DISCOVERY_PROBE_PAGE_SIZE: int = 1


def discover_annual_version(
    current_version: str,
    *,
    base_url: str = UCDP_GED_API_BASE,
    timeout: int = 30,
    max_retries: int = 3,
    token: str | None = None,
) -> str:
    """Probe the UCDP API for a newer annual version.

    Annual versions follow the pattern ``{major}.1`` (25.1, 26.1, …).
    Probes forward from the current major number until no data is found
    or the probe limit is reached.

    Returns the newest version with data, or *current_version* if
    nothing newer exists.
    """
    api_token = get_ucdp_token(token)
    current_major = int(current_version.split(".")[0])
    latest = current_version

    for major in range(
        current_major + 1,
        current_major + 1 + _ANNUAL_DISCOVERY_MAX_PROBES,
    ):
        probe_version = f"{major}.1"
        url = f"{base_url}/{probe_version}"
        headers = {"x-ucdp-access-token": api_token}
        params = {"pagesize": _ANNUAL_DISCOVERY_PROBE_PAGE_SIZE}

        try:
            resp = request_with_retry(
                url,
                headers=headers,
                params=params,
                max_retries=max_retries,
                timeout=timeout,
            )
        except requests.RequestException:
            logger.debug(
                "Annual version %s not available — stopping discovery",
                probe_version,
            )
            break

        data = resp.json()
        try:
            validate_envelope(data)
        except ValueError:
            logger.debug(
                "Annual version %s returned invalid envelope",
                probe_version,
            )
            break

        total = data["TotalCount"]
        if total == 0:
            logger.info(
                "Annual version %s has 0 events — stopping discovery",
                probe_version,
            )
            break

        latest = probe_version
        logger.info(
            "Discovered annual version %s (%d events)",
            probe_version,
            total,
        )

    return latest


# ---- Orchestrator ----


def _snapshot_path(config: UcdpAnnualConfig) -> Path:
    """Deterministic path for the raw event snapshot."""
    return (
        config.data_dir
        / f"ucdp_ged_v{config.version}_{config.start_year}_{config.end_year}.parquet"
    )


def fetch_ucdp_annual(
    config: UcdpAnnualConfig | None = None,
    *,
    token: str | None = None,
    force_refresh: bool = False,
) -> Path:
    """Fetch UCDP/GED Annual data: fetch -> validate -> compare -> store -> provenance.

    Args:
        config: Harvest configuration (defaults to standard PRIO range).
        token: API token (falls back to UCDP_API_TOKEN env var).
        force_refresh: If True, re-fetch even if snapshot exists.

    Returns:
        Path to the stored Parquet snapshot.
    """
    if config is None:
        config = UcdpAnnualConfig()

    # Probe for a newer annual release before checking the cache.
    discovered = discover_annual_version(
        config.version,
        base_url=config.base_url,
        timeout=config.timeout,
        max_retries=config.max_retries,
        token=token,
    )
    if discovered != config.version:
        new_major = int(discovered.split(".")[0])
        config = UcdpAnnualConfig(
            version=discovered,
            start_year=config.start_year,
            end_year=new_major + _YEAR_OFFSET,
            base_url=config.base_url,
            page_size=config.page_size,
            timeout=config.timeout,
            max_retries=config.max_retries,
            page_delay=config.page_delay,
            data_dir=config.data_dir,
            ledger_path=config.ledger_path,
        )
        logger.info(
            "Upgraded to annual version %s (end_year=%d)",
            discovered,
            config.end_year,
        )

    snap_path = _snapshot_path(config)

    # Digest-based short-circuit
    if not force_refresh and snap_path.exists():
        previous = last_digest(config.ledger_path)
        if previous is not None:
            logger.info(
                "Snapshot exists and ledger has digest; skipping fetch "
                "(use force_refresh=True to override)"
            )
            return snap_path

    # Fetch
    t0 = time.monotonic()
    events = fetch_paginated(config, token=token)
    fetch_duration = time.monotonic() - t0

    # Validate
    validation = validate_events(events, REQUIRED_FIELDS, FIELD_TYPES)

    # Compute actual date coverage
    min_date, max_date = date_range(events)

    base_entry = {
        "dataset": DATASET_ID,
        "version": config.version,
        "start_year": config.start_year,
        "end_year": config.end_year,
        "n_events": validation.n_events,
        "min_date_start": min_date,
        "max_date_start": max_date,
        "fetch_duration_s": round(
            fetch_duration, _FETCH_DURATION_PRECISION
        ),
        "content_digest": validation.content_digest,
        "ledger_version": LEDGER_VERSION,
        "digest_algorithm": DIGEST_SCHEME,
    }

    if not validation.valid:
        err_msg = f"Validation failed: {validation.errors}"
        logger.error(err_msg)
        append_ledger_entry(config.ledger_path, {
            **base_entry,
            "outcome": "failed",
            "errors": validation.errors,
            "warnings": validation.warnings,
        })
        raise ValueError(err_msg)

    validate_dgp_assumptions(
        events, UCDP_DGP_CHECKS, source_name="UCDP-annual",
    )

    # Compare with previous snapshot
    comparison: ComparisonResult | None = None
    if snap_path.exists():
        comparison = compare_snapshots(snap_path, events)
        if comparison.has_previous and comparison.n_revised == 0:
            logger.info("No revisions detected since previous snapshot")

    # Archive old snapshot if it exists
    if snap_path.exists():
        archive_snapshot(snap_path)

    # Store
    save_event_snapshot(events, snap_path)

    # Provenance
    revision_warnings = comparison.warnings if comparison else []
    append_ledger_entry(config.ledger_path, {
        **base_entry,
        "outcome": "success",
        "schema_fields": sorted(validation.schema_snapshot.keys()),
        "schema_types": validation.schema_snapshot,
        "warnings": validation.warnings + revision_warnings,
        "errors": validation.errors,
    })

    return snap_path


# Auto-register this source
register_source("ucdp_annual", fetch_ucdp_annual)
