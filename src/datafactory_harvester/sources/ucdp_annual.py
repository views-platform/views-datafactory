"""UCDP/GED Annual dataset source.

Fetches georeferenced event data from the Uppsala Conflict Data Program.
API docs: https://ucdp.uu.se/apidocs/

Source-specific concerns: API URL, schema definition, pagination,
token handling, version string. Uses the shared harvester skeleton
(validation, storage, provenance) from the parent package.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

from datafactory_harvester.event_validation import (
    ComparisonResult,
    compare_snapshots,
    date_range,
    validate_events,
)
from datafactory_harvester.snapshot_storage import archive_snapshot, save_event_snapshot
from datafactory_harvester.sources import register_source
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

ENVELOPE_KEYS: set[str] = {"TotalCount", "TotalPages", "Result"}

# Single source of truth for the UCDP GED API endpoint (ADR-003).
UCDP_GED_API_BASE: str = "https://ucdpapi.pcr.uu.se/api/gedevents"


# ---- Config ----


@dataclass(frozen=True)
class UcdpAnnualConfig:
    """Configuration for fetching UCDP/GED Annual data.

    Separates harvesting concerns from reporting concerns (SRP).
    No ranking_months, escalation_months, or top_n_countries here.
    """

    # Dataset identity
    version: str = "25.1"
    start_year: int = 1989
    end_year: int = 2024

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
        if self.end_year < self.start_year:
            err_msg = (
                f"end_year ({self.end_year}) must be >= "
                f"start_year ({self.start_year})"
            )
            logger.error(err_msg)
            raise ValueError(err_msg)
        if self.page_size < 1:
            err_msg = f"page_size must be >= 1, got {self.page_size}"
            logger.error(err_msg)
            raise ValueError(err_msg)
        if self.max_retries < 1:
            err_msg = f"max_retries must be >= 1, got {self.max_retries}"
            logger.error(err_msg)
            raise ValueError(err_msg)
        if self.page_delay <= 0:
            err_msg = f"page_delay must be > 0, got {self.page_delay}"
            logger.error(err_msg)
            raise ValueError(err_msg)
        if self.timeout < 1:
            err_msg = f"timeout must be >= 1, got {self.timeout}"
            logger.error(err_msg)
            raise ValueError(err_msg)
        if not self.version:
            err_msg = "version must be non-empty"
            logger.error(err_msg)
            raise ValueError(err_msg)


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



def validate_envelope(data: dict) -> None:
    """Validate the API response envelope structure."""
    missing = ENVELOPE_KEYS - set(data.keys())
    if missing:
        err_msg = (
            f"UCDP API response envelope missing keys: {missing}. "
            f"Available keys: {sorted(data.keys())}."
        )
        logger.error(err_msg)
        raise ValueError(err_msg)
    if not isinstance(data["Result"], list):
        err_msg = (
            f"UCDP API 'Result' is {type(data['Result']).__name__}, expected list."
        )
        logger.error(err_msg)
        raise ValueError(err_msg)


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
        response = request_with_retry(
            url,
            headers=headers,
            params=params,
            max_retries=config.max_retries,
            timeout=config.timeout,
        )
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

    # Assert fetched count against API's TotalCount. The API may
    # count events it doesn't return (e.g., type_of_violence=4),
    # so allow up to 1% shortfall. A larger gap indicates a silent
    # partial fetch (rate limiting, pagination failure).
    if max_pages is None and total_count and total_count > 0:
        shortfall = total_count - len(all_events)
        shortfall_pct = shortfall / total_count
        if shortfall_pct > 0.01:
            err_msg = (
                f"Fetch count mismatch: API reports {total_count} "
                f"events but only {len(all_events)} fetched "
                f"({shortfall_pct:.1%} shortfall). "
                f"Likely a silent partial fetch due to rate limiting."
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
