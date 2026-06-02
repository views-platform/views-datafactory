"""ACLED (Armed Conflict Location & Event Data) source.

Fetches event-level conflict and protest data from the ACLED API.
API docs: https://apidocs.acleddata.com/

Authentication: OAuth2 password grant (ADR-026). Each user must
authenticate with their own credentials — credential sharing is
prohibited by ACLED's EULA.

Source-specific concerns: OAuth token lifecycle, event type taxonomy,
daily granularity, pagination via page parameter. Uses the shared
harvester skeleton (validation, storage, provenance).
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import requests

from datafactory_harvester.event_validation import (
    ComparisonResult,
    compare_snapshots,
    date_range,
    validate_events,
)
from datafactory_harvester.snapshot_storage import (
    archive_snapshot,
    save_event_snapshot,
)
from datafactory_harvester.sources import register_source
from datafactory_harvester.validation import (
    validate_positive_float,
    validate_positive_int,
    validate_year_range,
)
from datafactory_http import request_with_retry
from datafactory_provenance import (
    DIGEST_SCHEME,
    LEDGER_VERSION,
    append_ledger_entry,
    compute_content_digest,
    last_digest_for_version,
)

logger = logging.getLogger(__name__)

DATASET_ID = "acled"
_LOG_EVERY_N_PAGES: int = 10
_FETCH_DURATION_PRECISION: int = 1
_TOKEN_REFRESH_MARGIN_S: float = 300.0  # Refresh 5 min before expiry

ACLED_API_BASE = "https://acleddata.com/api/acled/read"
ACLED_TOKEN_URL = "https://acleddata.com/oauth/token"

ALL_EVENT_TYPES: tuple[str, ...] = (
    "Battles",
    "Explosions/Remote violence",
    "Violence against civilians",
    "Protests",
    "Riots",
    "Strategic developments",
)

# ---- ACLED schema definition (preliminary, from documentation) ----

REQUIRED_FIELDS: set[str] = {
    "event_id_cnty",
    "event_date",
    "event_type",
    "sub_event_type",
    "actor1",
    "country",
    "latitude",
    "longitude",
    "fatalities",
}

# Preliminary types from ACLED docs — tighten after Phase 2 API investigation.
FIELD_TYPES: dict[str, tuple[type, ...]] = {
    "event_id_cnty": (str,),
    "event_date": (str,),
    "event_type": (str,),
    "sub_event_type": (str,),
    "actor1": (str,),
    "actor2": (str,),
    "country": (str,),
    "admin1": (str,),
    "latitude": (str, float, int),
    "longitude": (str, float, int),
    "fatalities": (int, float, str),
    "notes": (str,),
    "source": (str,),
    "source_scale": (str,),
}


# ---- Config ----


@dataclass(frozen=True)
class AcledConfig:
    """Configuration for fetching ACLED event data."""

    start_year: int = 1997
    end_year: int = 2025

    event_types: tuple[str, ...] = ALL_EVENT_TYPES

    # API transport
    api_url: str = ACLED_API_BASE
    token_url: str = ACLED_TOKEN_URL
    page_size: int = 5000
    timeout: int = 60
    max_retries: int = 3
    page_delay: float = 2.0

    # Storage
    data_dir: Path = Path("data/raw/acled")
    ledger_path: Path = Path("provenance/acled/ingestion_ledger.jsonl")

    def __post_init__(self) -> None:
        validate_year_range(self.start_year, self.end_year)
        validate_positive_int(self.page_size, "page_size")
        validate_positive_int(self.max_retries, "max_retries")
        validate_positive_float(self.page_delay, "page_delay")
        validate_positive_int(self.timeout, "timeout")
        for et in self.event_types:
            if et not in ALL_EVENT_TYPES:
                msg = (
                    f"Unknown event type '{et}'. "
                    f"Valid: {ALL_EVENT_TYPES}"
                )
                raise ValueError(msg)


# ---- Credential resolution (ADR-026) ----


def get_acled_credentials(
    username: str | None = None,
    password: str | None = None,
) -> tuple[str, str]:
    """Resolve ACLED credentials from arguments or environment.

    Resolution order (per ADR-026):
    1. Function arguments (highest priority)
    2. Environment variables ACLED_USERNAME / ACLED_PASSWORD
    3. Fail-loud with actionable error message

    Returns:
        (username, password) tuple.

    Raises:
        ValueError: If credentials cannot be resolved.
    """
    resolved_user = username or os.environ.get("ACLED_USERNAME")
    resolved_pass = password or os.environ.get("ACLED_PASSWORD")

    missing = []
    if not resolved_user:
        missing.append("ACLED_USERNAME")
    if not resolved_pass:
        missing.append("ACLED_PASSWORD")

    if missing:
        err_msg = (
            f"ACLED credentials required. Set {' and '.join(missing)} "
            "environment variable(s) or pass username=/password= to "
            "fetch_acled()."
        )
        logger.error(err_msg)
        raise ValueError(err_msg)

    return resolved_user, resolved_pass  # type: ignore[return-value]


# ---- OAuth2 token management ----


@dataclass
class _TokenState:
    """Mutable token state — NOT in frozen config (ADR-026)."""

    access_token: str = ""
    expires_at: float = 0.0

    @property
    def is_valid(self) -> bool:
        return (
            bool(self.access_token)
            and time.monotonic() < self.expires_at - _TOKEN_REFRESH_MARGIN_S
        )


def _acquire_token(
    username: str,
    password: str,
    token_url: str = ACLED_TOKEN_URL,
    timeout: int = 30,
    max_retries: int = 3,
) -> _TokenState:
    """Acquire a new OAuth2 bearer token from ACLED."""
    response = request_with_retry(
        token_url,
        method="POST",
        data={
            "client_id": "acled",
            "username": username,
            "password": password,
            "grant_type": "password",
        },
        max_retries=max_retries,
        timeout=timeout,
    )
    token_data = response.json()

    access_token = token_data.get("access_token")
    if not access_token:
        err_msg = (
            "ACLED token response missing 'access_token'. "
            f"Response keys: {sorted(token_data.keys())}"
        )
        logger.error(err_msg)
        raise ValueError(err_msg)

    expires_in = int(token_data.get("expires_in", 86400))
    expires_at = time.monotonic() + expires_in

    logger.info(
        "ACLED token acquired (expires in %ds)", expires_in
    )
    return _TokenState(
        access_token=access_token, expires_at=expires_at
    )


def _ensure_token(
    state: _TokenState,
    username: str,
    password: str,
    token_url: str = ACLED_TOKEN_URL,
    timeout: int = 30,
    max_retries: int = 3,
) -> _TokenState:
    """Return a valid token, refreshing if near expiry."""
    if state.is_valid:
        return state
    logger.info("ACLED token expired or near expiry, refreshing")
    return _acquire_token(
        username, password, token_url, timeout, max_retries
    )


# ---- API client ----


def _authenticated_request(
    url: str,
    params: dict,
    state: _TokenState,
    username: str,
    password: str,
    token_url: str,
    timeout: int,
    max_retries: int,
) -> tuple[requests.Response, _TokenState]:
    """Make an authenticated request, recovering from 401.

    Handles the full OAuth2 token lifecycle:
    1. Proactive refresh if local clock says token is near expiry
    2. Reactive recovery if the server returns 401

    Returns the response and the (possibly refreshed) token state.
    Credentials are passed as arguments, never stored (ADR-026).
    """
    state = _ensure_token(
        state, username, password,
        token_url, timeout, max_retries,
    )

    def _do_request(s: _TokenState) -> requests.Response:
        return request_with_retry(
            url,
            headers={
                "Authorization": f"Bearer {s.access_token}",
                "User-Agent": (
                    "VIEWS-DataFactory/1.0 (monthly-cron)"
                ),
            },
            params=params,
            max_retries=max_retries,
            timeout=timeout,
        )

    try:
        return _do_request(state), state
    except requests.HTTPError as exc:
        if (
            exc.response is not None
            and exc.response.status_code == 401
        ):
            logger.warning(
                "401 from %s — forcing token refresh", url,
            )
            state = _acquire_token(
                username, password,
                token_url, timeout, max_retries,
            )
            return _do_request(state), state
        raise


def fetch_paginated(
    config: AcledConfig,
    username: str,
    password: str,
    *,
    max_pages: int | None = None,
    _token_state: _TokenState | None = None,
) -> list[dict]:
    """Fetch all ACLED events with page-based pagination.

    Args:
        config: Harvest configuration.
        username: ACLED username.
        password: ACLED password.
        max_pages: Stop after this many pages (None = fetch all).
        _token_state: Pre-acquired token (avoids re-auth per year).

    Returns:
        List of raw event dicts.
    """
    token_state = _token_state or _acquire_token(
        username,
        password,
        config.token_url,
        config.timeout,
        config.max_retries,
    )

    all_events: list[dict] = []
    page = 1

    while True:
        params: dict = {
            "_format": "json",
            "event_date": (
                f"{config.start_year}-01-01"
                f"|{config.end_year}-12-31"
            ),
            "event_date_where": "BETWEEN",
            "limit": config.page_size,
            "page": page,
        }

        if config.event_types != ALL_EVENT_TYPES:
            params["event_type"] = "|".join(config.event_types)

        response, token_state = _authenticated_request(
            config.api_url,
            params,
            token_state,
            username,
            password,
            config.token_url,
            config.timeout,
            config.max_retries,
        )
        data = response.json()

        results = data.get("data", [])
        if not results:
            break

        all_events.extend(results)

        if page % _LOG_EVERY_N_PAGES == 0 or page == 1:
            logger.info(
                "Page %d: %d events fetched so far",
                page,
                len(all_events),
            )

        if len(results) < config.page_size:
            break
        if max_pages is not None and page >= max_pages:
            logger.info(
                "Stopped after %d pages (max_pages limit)",
                max_pages,
            )
            break

        page += 1
        time.sleep(config.page_delay)

    logger.info(
        "Fetched %d total ACLED events across %d pages",
        len(all_events),
        page,
    )
    return all_events


# ---- Orchestrator ----

DIGEST_FIELDS: tuple[str, ...] = ("event_id_cnty", "fatalities")


def _snapshot_path(config: AcledConfig) -> Path:
    """Deterministic path for the raw event snapshot."""
    return (
        config.data_dir
        / f"acled_{config.start_year}_{config.end_year}.parquet"
    )


def _recompute_content_digest(snap_path: Path) -> str | None:
    """Recompute content_digest from a Parquet snapshot on disk.

    Uses the same algorithm as event_validation.py: sorted tuples of
    digest fields → JSON → SHA-256. Returns None if the file cannot
    be read (corrupted, missing columns).
    """
    try:
        table = pq.read_table(
            snap_path, columns=list(DIGEST_FIELDS),
        )
    except (pa.lib.ArrowInvalid, OSError):
        logger.warning(
            "Cannot read %s for digest — treating as cache miss",
            snap_path,
        )
        return None
    digest_data = sorted(
        tuple(row) for row in zip(
            *(table.column(f).to_pylist() for f in DIGEST_FIELDS),
            strict=True,
        )
    )
    return compute_content_digest(
        json.dumps(digest_data, sort_keys=True).encode()
    )


def _year_is_cached(year: int, config: AcledConfig) -> bool:
    """Check if a year's snapshot exists with a matching ledger digest."""
    version = f"{year}_{year}"
    snap_path = config.data_dir / f"acled_{year}_{year}.parquet"
    if not snap_path.exists():
        return False
    previous = last_digest_for_version(
        config.ledger_path, version
    )
    if previous is None:
        return False
    actual = _recompute_content_digest(snap_path)
    if actual is None:
        return False
    if actual != previous:
        logger.warning(
            "Year %d cached content digest mismatch "
            "(expected %s, got %s) — re-fetching",
            year, previous, actual,
        )
        return False
    return True


def _fetch_single_year(
    year: int,
    config: AcledConfig,
    resolved_user: str,
    resolved_pass: str,
    token_state: _TokenState,
) -> dict:
    """Fetch one year of ACLED data: fetch, validate, store.

    Returns a result dict with version, outcome, and path info.
    """
    version = f"{year}_{year}"
    year_config = AcledConfig(
        start_year=year,
        end_year=year,
        event_types=config.event_types,
        api_url=config.api_url,
        token_url=config.token_url,
        page_size=config.page_size,
        timeout=config.timeout,
        max_retries=config.max_retries,
        page_delay=config.page_delay,
        data_dir=config.data_dir,
        ledger_path=config.ledger_path,
    )
    snap_path = _snapshot_path(year_config)

    t0 = time.monotonic()
    events = fetch_paginated(
        year_config,
        resolved_user,
        resolved_pass,
        _token_state=token_state,
    )
    fetch_duration = time.monotonic() - t0

    validation = validate_events(
        events,
        REQUIRED_FIELDS,
        FIELD_TYPES,
        digest_fields=DIGEST_FIELDS,
    )

    min_date, max_date = date_range(
        events, field_name="event_date"
    )

    base_entry = {
        "dataset": DATASET_ID,
        "version": version,
        "start_year": year,
        "end_year": year,
        "n_events": validation.n_events,
        "min_date": min_date,
        "max_date": max_date,
        "fetch_duration_s": round(
            fetch_duration, _FETCH_DURATION_PRECISION
        ),
        "content_digest": validation.content_digest,
        "ledger_version": LEDGER_VERSION,
        "digest_algorithm": DIGEST_SCHEME,
    }

    if not validation.valid:
        err_msg = (
            f"Validation failed for year {year}: "
            f"{validation.errors}"
        )
        logger.error(err_msg)
        append_ledger_entry(config.ledger_path, {
            **base_entry,
            "outcome": "failed",
            "errors": validation.errors,
            "warnings": validation.warnings,
        })
        raise ValueError(err_msg)

    comparison: ComparisonResult | None = None
    if snap_path.exists():
        comparison = compare_snapshots(
            snap_path,
            events,
            id_field="event_id_cnty",
            key_fields=("fatalities", "country", "event_date"),
        )
        if comparison.has_previous and comparison.n_revised == 0:
            logger.info(
                "Year %d: no revisions since previous snapshot",
                year,
            )

    if snap_path.exists():
        archive_snapshot(snap_path)

    save_event_snapshot(events, snap_path)

    revision_warnings = comparison.warnings if comparison else []
    append_ledger_entry(config.ledger_path, {
        **base_entry,
        "outcome": "success",
        "schema_fields": sorted(validation.schema_snapshot.keys()),
        "schema_types": validation.schema_snapshot,
        "warnings": validation.warnings + revision_warnings,
        "errors": validation.errors,
    })

    return {
        "version": version,
        "outcome": "success",
        "digest": validation.content_digest,
        "path": str(snap_path),
        "n_events": validation.n_events,
    }


def fetch_acled(
    config: AcledConfig | None = None,
    *,
    username: str | None = None,
    password: str | None = None,
    force_refresh: bool = False,
) -> Path:
    """Fetch ACLED data year-by-year: auth, then per-year fetch/skip.

    Each year gets its own snapshot and version-aware ledger entry.
    Cached years (snapshot + ledger digest) are skipped, so monthly
    cron runs only fetch the current year.

    Args:
        config: Harvest configuration (defaults to full range).
        username: ACLED username (falls back to ACLED_USERNAME env var).
        password: ACLED password (falls back to ACLED_PASSWORD env var).
        force_refresh: If True, re-fetch even if snapshot exists.

    Returns:
        Path to the data directory containing per-year snapshots.
    """
    if config is None:
        config = AcledConfig()

    resolved_user, resolved_pass = get_acled_credentials(
        username, password
    )

    token_state: _TokenState | None = None

    results = []
    for year in range(config.start_year, config.end_year + 1):
        if not force_refresh and _year_is_cached(
            year, config
        ):
            version = f"{year}_{year}"
            logger.info("Year %d cached, skipping", year)
            results.append({
                "version": version,
                "outcome": "cached",
            })
            continue

        if token_state is None:
            token_state = _acquire_token(
                resolved_user,
                resolved_pass,
                config.token_url,
                config.timeout,
                config.max_retries,
            )
        else:
            token_state = _ensure_token(
                token_state,
                resolved_user,
                resolved_pass,
                config.token_url,
                config.timeout,
                config.max_retries,
            )

        result = _fetch_single_year(
            year,
            config,
            resolved_user,
            resolved_pass,
            token_state,
        )
        results.append(result)

    cached = sum(1 for r in results if r["outcome"] == "cached")
    fetched = sum(
        1 for r in results if r["outcome"] == "success"
    )
    logger.info(
        "ACLED harvest: %d years total, %d cached, %d fetched",
        len(results),
        cached,
        fetched,
    )

    return config.data_dir


register_source("acled", fetch_acled)
