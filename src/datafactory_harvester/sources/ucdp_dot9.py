"""UCDP/GED .9 consolidated monthly dataset source.

Fetches the .9 version of UCDP conflict event data — a bespoke
monthly release produced by UCDP that contains exclusive events
not available in standard annual or candidate releases.

See reports/dot9_investigation/ for empirical findings.

Key differences from candidate:
- Version format: YY.9.MM (e.g., "25.9.11") instead of YY.0.MM
- Contains exclusive events not in standard releases (count varies by version and year)
- Undocumented by UCDP — no codebook or specification exists
- Production VIEWS forecasting depends on this data stream
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from datafactory_harvester.event_validation import (
    compare_snapshots,
    validate_events,
)
from datafactory_harvester.snapshot_storage import (
    archive_snapshot,
    save_event_snapshot,
)
from datafactory_harvester.sources import register_source
from datafactory_harvester.sources.ucdp_annual import (
    FIELD_TYPES,
    REQUIRED_FIELDS,
    UcdpAnnualConfig,
    fetch_paginated,
    get_ucdp_token,
)
from datafactory_http import request_with_retry
from datafactory_provenance import (
    DIGEST_SCHEME,
    LEDGER_VERSION,
    append_ledger_entry,
    last_digest_for_version,
)

logger = logging.getLogger(__name__)

DATASET_ID = "ucdp_dot9"
_DOT9_YEAR_OFFSET: int = 2000
_DISCOVERY_RATE_LIMIT_SECONDS: float = 0.5
_DISCOVERY_PROBE_PAGE_SIZE: int = 1

# .9 data availability (empirically confirmed 2026-03-21)
DOT9_FIRST_YEAR: int = 2018
DOT9_FIRST_MONTH: int = 1
_DEFAULT_MAX_VERSIONS: int = 120
_FETCH_DATE_RANGE_START: int = 2000
_FETCH_DATE_RANGE_END: int = 2099
_FETCH_DURATION_PRECISION: int = 1


def _dot9_version_string(year: int, month: int) -> str:
    """Build a .9 monthly version string.

    Format: "{year-2000}.9.{month}" — e.g., 2025/1 → "25.9.1".
    """
    return f"{year - _DOT9_YEAR_OFFSET}.9.{month}"


# ---- Config ----


@dataclass(frozen=True)
class UcdpDot9Config:
    """Configuration for fetching UCDP/GED .9 consolidated data.

    Same structure as UcdpCandidateConfig but for the .9 stream.
    Versions are discovered automatically from start_year/month.
    """

    # Discovery start
    start_year: int = DOT9_FIRST_YEAR
    start_month: int = DOT9_FIRST_MONTH

    # API transport
    base_url: str = (
        "https://ucdpapi.pcr.uu.se/api/gedevents"
    )
    page_size: int = 1000
    timeout: int = 30
    max_retries: int = 3

    # Discovery tuning
    discovery_rate_limit: float = _DISCOVERY_RATE_LIMIT_SECONDS
    max_versions: int = _DEFAULT_MAX_VERSIONS

    # Storage
    data_dir: Path = Path("data/raw/ucdp_dot9")
    ledger_path: Path = Path(
        "provenance/ucdp_dot9/ingestion_ledger.jsonl"
    )

    def __post_init__(self) -> None:
        if not (1 <= self.start_month <= 12):
            err_msg = (
                f"start_month must be in [1, 12], "
                f"got {self.start_month}"
            )
            logger.error(err_msg)
            raise ValueError(err_msg)
        if self.start_year < 1:
            err_msg = (
                f"start_year must be >= 1, "
                f"got {self.start_year}"
            )
            logger.error(err_msg)
            raise ValueError(err_msg)
        if self.page_size < 1:
            err_msg = (
                f"page_size must be >= 1, "
                f"got {self.page_size}"
            )
            logger.error(err_msg)
            raise ValueError(err_msg)
        if self.max_retries < 1:
            err_msg = (
                f"max_retries must be >= 1, "
                f"got {self.max_retries}"
            )
            logger.error(err_msg)
            raise ValueError(err_msg)
        if self.discovery_rate_limit <= 0:
            err_msg = (
                f"discovery_rate_limit must be > 0, "
                f"got {self.discovery_rate_limit}"
            )
            logger.error(err_msg)
            raise ValueError(err_msg)
        if self.max_versions < 1:
            err_msg = (
                f"max_versions must be >= 1, "
                f"got {self.max_versions}"
            )
            logger.error(err_msg)
            raise ValueError(err_msg)


# ---- Version Discovery ----


def discover_dot9_versions(
    config: UcdpDot9Config,
    *,
    token: str | None = None,
) -> list[str]:
    """Discover available .9 monthly versions by probing the API.

    Starts from config.start_year/start_month and probes forward
    month by month until a version returns no data.

    Args:
        config: .9 configuration.
        token: API token (falls back to UCDP_API_TOKEN env var).

    Returns:
        Sorted list of available version strings.
    """
    api_token = get_ucdp_token(token)
    versions: list[str] = []

    year = config.start_year
    month = config.start_month

    for _ in range(config.max_versions):
        version = _dot9_version_string(year, month)
        url = f"{config.base_url}/{version}"
        headers = {"x-ucdp-access-token": api_token}
        params = {"pagesize": _DISCOVERY_PROBE_PAGE_SIZE}

        try:
            resp = request_with_retry(
                url,
                headers=headers,
                params=params,
                max_retries=config.max_retries,
                timeout=config.timeout,
            )
            data = resp.json()
            total = data.get("TotalCount", 0)
            if total == 0:
                logger.info(
                    "Version %s has 0 events — stopping",
                    version,
                )
                break
            versions.append(version)
            logger.info(
                "Discovered .9 version %s (%d events)",
                version, total,
            )
            time.sleep(config.discovery_rate_limit)
        except (requests.RequestException, ValueError):
            logger.debug(
                "Version %s not available — stopping",
                version,
            )
            break

        month += 1
        if month > 12:
            month = 1
            year += 1

    return versions


# ---- Fetch ----


def _snapshot_path(
    config: UcdpDot9Config, version: str
) -> Path:
    """Build the Parquet snapshot path for a .9 version."""
    return config.data_dir / f"ucdp_ged_dot9_{version}.parquet"


def _fetch_dot9_version(
    config: UcdpDot9Config,
    version: str,
    *,
    token: str | None = None,
    force_refresh: bool = False,
) -> dict:
    """Fetch a single .9 monthly version.

    Local-first: if the snapshot file exists and the ledger has a
    matching digest, skip without touching the API. This makes
    re-runs near-instant for already-fetched versions.

    Returns a result dict with version, outcome, digest, and path.
    """
    snap_path = _snapshot_path(config, version)

    # Local-first skip: file exists + ledger has digest → skip API
    if not force_refresh and snap_path.exists():
        previous = last_digest_for_version(
            config.ledger_path, version
        )
        if previous is not None:
            logger.info(
                "Version %s already on disk (digest: %s)",
                version, previous,
            )
            return {
                "version": version,
                "outcome": "cached",
                "digest": previous,
                "path": str(snap_path),
            }

    annual_config = UcdpAnnualConfig(
        version=version,
        start_year=_FETCH_DATE_RANGE_START,
        end_year=_FETCH_DATE_RANGE_END,
        base_url=config.base_url,
        page_size=config.page_size,
        timeout=config.timeout,
        max_retries=config.max_retries,
        data_dir=config.data_dir,
        ledger_path=config.ledger_path,
    )

    # Fetch from API
    t0 = time.monotonic()
    events = fetch_paginated(annual_config, token=token)
    fetch_duration = time.monotonic() - t0

    # Validate
    validation = validate_events(
        events, REQUIRED_FIELDS, FIELD_TYPES
    )

    # Compute actual date coverage
    dates = [
        e.get("date_start") for e in events
        if e.get("date_start")
    ]
    min_date: str | None = min(dates) if dates else None  # type: ignore[type-var]
    max_date: str | None = max(dates) if dates else None  # type: ignore[type-var]

    base_entry = {
        "dataset": DATASET_ID,
        "version": version,
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
        err_msg = (
            f"Validation failed for {version}: "
            f"{validation.errors}"
        )
        logger.error(err_msg)
        append_ledger_entry(config.ledger_path, {
            **base_entry,
            "outcome": "failed",
            "errors": validation.errors,
            "warnings": validation.warnings,
        })
        return {
            "version": version,
            "outcome": "failed",
            "errors": validation.errors,
        }

    # Digest-based caching
    previous = last_digest_for_version(
        config.ledger_path, version
    )
    changed = (
        previous is None
        or previous != validation.content_digest
    )

    if not changed and not force_refresh:
        logger.info(
            "Version %s unchanged (digest: %s)",
            version, validation.content_digest,
        )
        append_ledger_entry(config.ledger_path, {
            **base_entry,
            "outcome": "unchanged",
        })
        return {
            "version": version,
            "outcome": "unchanged",
            "digest": validation.content_digest,
        }

    # Compare + archive + store
    comparison = None
    if snap_path.exists():
        comparison = compare_snapshots(snap_path, events)
        if comparison.has_previous:
            logger.info(
                "Version %s: %d added, %d removed, %d revised",
                version,
                comparison.n_added,
                comparison.n_removed,
                comparison.n_revised,
            )
        archive_snapshot(snap_path)

    save_event_snapshot(events, snap_path)

    revision_warnings = (
        comparison.warnings if comparison else []
    )
    append_ledger_entry(config.ledger_path, {
        **base_entry,
        "outcome": "success",
        "schema_fields": sorted(
            validation.schema_snapshot.keys()
        ),
        "warnings": validation.warnings + revision_warnings,
        "errors": validation.errors,
    })

    return {
        "version": version,
        "outcome": "success",
        "digest": validation.content_digest,
        "n_events": validation.n_events,
        "path": str(snap_path),
    }


def fetch_ucdp_dot9(
    config: UcdpDot9Config | None = None,
    *,
    token: str | None = None,
    force_refresh: bool = False,
) -> list[dict]:
    """Fetch all available .9 monthly versions.

    Discovers versions by probing the API forward from
    config.start_year/start_month, then fetches each.

    Args:
        config: .9 configuration. Uses defaults if None.
        token: API token (falls back to UCDP_API_TOKEN env var).
        force_refresh: Re-fetch even if digest unchanged.

    Returns:
        List of result dicts, one per version fetched.
    """
    if config is None:
        config = UcdpDot9Config()

    versions = discover_dot9_versions(config, token=token)
    logger.info("Discovered %d .9 versions", len(versions))

    results: list[dict] = []
    for version in versions:
        result = _fetch_dot9_version(
            config, version,
            token=token, force_refresh=force_refresh,
        )
        results.append(result)

    return results


# Auto-register
register_source("ucdp_dot9", fetch_ucdp_dot9)
