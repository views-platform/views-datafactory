"""UCDP/GED Candidate Monthly dataset source.

Fetches georeferenced event data from candidate monthly releases.
These are in-flight revisions that may change between monthly releases.

Key differences from annual:
- Multi-version: each month is a separate version (e.g., "25.0.1")
- Version discovery: probes API forward until no data found
- Digest caching: skips expensive operations if content unchanged
- Per-version provenance: each version gets its own ledger entry
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from datafactory_core import (
    append_ledger_entry,
    last_digest_for_version,
)
from datafactory_harvester.sources import register_source
from datafactory_harvester.sources.ucdp_annual import (
    FIELD_TYPES,
    REQUIRED_FIELDS,
    UcdpAnnualConfig,
    fetch_paginated,
    request_with_retry,
)
from datafactory_harvester.storage import archive_snapshot, save_event_snapshot
from datafactory_harvester.validation import (
    compare_snapshots,
    validate_events,
)

logger = logging.getLogger(__name__)


def _candidate_version_string(year: int, month: int) -> str:
    """Build a candidate monthly version string.

    Format: "{year-2000}.0.{month}" — e.g., 2025/1 → "25.0.1".
    Caller is responsible for valid year/month ranges
    (validated in UcdpCandidateConfig.__post_init__).
    """
    return f"{year - 2000}.0.{month}"


# ---- Config ----


@dataclass(frozen=True)
class UcdpCandidateConfig:
    """Configuration for fetching UCDP/GED Candidate Monthly data.

    No version field — versions are discovered automatically.
    start_year/start_month define the beginning of the discovery window.
    """

    # Discovery start
    start_year: int = 2025
    start_month: int = 1

    # API transport (reuse annual defaults)
    base_url: str = "https://ucdpapi.pcr.uu.se/api/gedevents"
    page_size: int = 1000
    timeout: int = 30
    max_retries: int = 3

    # Storage
    data_dir: Path = Path("data/ucdp_candidate")
    ledger_path: Path = Path(
        "provenance/ucdp_candidate/ingestion_ledger.jsonl"
    )

    def __post_init__(self) -> None:
        if not (1 <= self.start_month <= 12):
            err_msg = (
                f"start_month must be in [1, 12], got {self.start_month}"
            )
            logger.error(err_msg)
            raise ValueError(err_msg)
        if self.start_year < 1:
            err_msg = f"start_year must be >= 1, got {self.start_year}"
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


# ---- Version Discovery ----


def discover_versions(
    config: UcdpCandidateConfig,
    *,
    token: str | None = None,
    max_versions: int = 36,
) -> list[str]:
    """Discover available candidate monthly versions by probing the API.

    Starts from config.start_year/start_month and probes forward
    month by month until a version returns no data.

    Args:
        config: Candidate monthly configuration.
        token: API token (falls back to UCDP_API_TOKEN env var).
        max_versions: Safety limit on discovery (default 36 months).

    Returns:
        Sorted list of available version strings.
    """
    from datafactory_harvester.sources.ucdp_annual import get_ucdp_token

    api_token = get_ucdp_token(token)
    versions: list[str] = []

    year = config.start_year
    month = config.start_month

    for _ in range(max_versions):
        version = _candidate_version_string(year, month)
        url = f"{config.base_url}/{version}"
        headers = {"x-ucdp-access-token": api_token}
        params = {"pagesize": 1}

        try:
            resp = request_with_retry(
                url,
                headers,
                params,
                max_retries=config.max_retries,
                timeout=config.timeout,
            )
            data = resp.json()
            total = data.get("TotalCount", 0)
            if total == 0:
                logger.info(
                    "Version %s has 0 events — stopping discovery",
                    version,
                )
                break
            versions.append(version)
            logger.info(
                "Discovered version %s (%d events)", version, total
            )
            time.sleep(0.5)  # Rate-limit discovery probes
        except Exception:
            logger.info(
                "Version %s not available — stopping discovery", version
            )
            break

        # Advance month
        month += 1
        if month > 12:
            month = 1
            year += 1

    return versions


# ---- Per-Version Fetch ----


def _snapshot_path(config: UcdpCandidateConfig, version: str) -> Path:
    """Deterministic path for a version's event snapshot."""
    return config.data_dir / f"ucdp_ged_candidate_{version}.parquet"


def _fetch_version(
    config: UcdpCandidateConfig,
    version: str,
    *,
    token: str | None = None,
    force_refresh: bool = False,
) -> dict:
    """Fetch a single candidate monthly version.

    Returns a result dict with version, outcome, digest, and path info.
    """
    # Build a temporary annual-style config for the shared fetch_paginated.
    # Date range is a wide superset — candidate versions select data by
    # version string, not by date. The range ensures no events are filtered.
    annual_config = UcdpAnnualConfig(
        version=version,
        start_year=2000,
        end_year=2099,
        base_url=config.base_url,
        page_size=config.page_size,
        timeout=config.timeout,
        max_retries=config.max_retries,
        data_dir=config.data_dir,
        ledger_path=config.ledger_path,
    )

    snap_path = _snapshot_path(config, version)

    # Fetch events
    t0 = time.monotonic()
    events = fetch_paginated(annual_config, token=token)
    fetch_duration = time.monotonic() - t0

    # Validate
    validation = validate_events(events, REQUIRED_FIELDS, FIELD_TYPES)

    base_entry = {
        "dataset": "ucdp_candidate",
        "version": version,
        "n_events": validation.n_events,
        "fetch_duration_s": round(fetch_duration, 1),
        "content_digest": validation.content_digest,
    }

    if not validation.valid:
        err_msg = f"Validation failed for {version}: {validation.errors}"
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
    previous_digest = last_digest_for_version(
        config.ledger_path, version
    )
    digest_changed = (
        previous_digest is None
        or previous_digest != validation.content_digest
    )

    if not digest_changed and not force_refresh:
        logger.info(
            "Version %s unchanged (digest: %s), recording heartbeat",
            version,
            validation.content_digest,
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

    # Compare, archive, store
    if snap_path.exists():
        compare_snapshots(snap_path, events)
        archive_snapshot(snap_path)

    save_event_snapshot(events, snap_path)

    # Provenance
    append_ledger_entry(config.ledger_path, {
        **base_entry,
        "outcome": "success",
        "schema_fields": sorted(validation.schema_snapshot.keys()),
        "warnings": validation.warnings,
        "errors": validation.errors,
    })

    return {
        "version": version,
        "outcome": "success",
        "digest": validation.content_digest,
        "n_events": validation.n_events,
        "path": str(snap_path),
    }


# ---- Orchestrator ----


def fetch_ucdp_candidate(
    config: UcdpCandidateConfig | None = None,
    *,
    token: str | None = None,
    force_refresh: bool = False,
) -> list[dict]:
    """Fetch all available UCDP/GED Candidate Monthly versions.

    Discovers available versions, then fetches each one independently
    with digest-based caching.

    Args:
        config: Candidate monthly configuration.
        token: API token (falls back to UCDP_API_TOKEN env var).
        force_refresh: If True, re-fetch even if digests match.

    Returns:
        List of per-version result dicts.
    """
    if config is None:
        config = UcdpCandidateConfig()

    versions = discover_versions(config, token=token)
    if not versions:
        logger.warning("No candidate monthly versions discovered")
        return []

    logger.info("Discovered %d candidate monthly versions", len(versions))

    results = []
    for version in versions:
        result = _fetch_version(
            config, version, token=token, force_refresh=force_refresh
        )
        results.append(result)

    n_success = sum(1 for r in results if r["outcome"] == "success")
    n_unchanged = sum(1 for r in results if r["outcome"] == "unchanged")
    n_failed = sum(1 for r in results if r["outcome"] == "failed")
    logger.info(
        "Candidate monthly fetch complete: %d success, %d unchanged, "
        "%d failed",
        n_success,
        n_unchanged,
        n_failed,
    )

    return results


# Auto-register this source
register_source("ucdp_candidate", fetch_ucdp_candidate)
