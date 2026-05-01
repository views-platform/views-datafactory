"""ACLED (Armed Conflict Location & Event Data) source.

Fetches event-level conflict and protest data from the ACLED API.
API docs: https://apidocs.acleddata.com/

Authentication: OAuth2 password grant (ADR-026). Each user must
authenticate with their own credentials — credential sharing is
prohibited by ACLED's EULA.

Source-specific concerns: OAuth token lifecycle, event type taxonomy,
daily granularity, pagination via limit/offset. Uses the shared
harvester skeleton (validation, storage, provenance).
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
from datafactory_harvester.snapshot_storage import (
    archive_snapshot,
    save_event_snapshot,
)
from datafactory_harvester.sources import register_source
from datafactory_http import request_with_retry
from datafactory_provenance import (
    DIGEST_SCHEME,
    LEDGER_VERSION,
    append_ledger_entry,
    last_digest,
)

logger = logging.getLogger(__name__)

DATASET_ID = "acled"
_LOG_EVERY_N_PAGES: int = 10
_FETCH_DURATION_PRECISION: int = 1
_TOKEN_REFRESH_MARGIN_S: float = 300.0  # Refresh 5 min before expiry

ACLED_API_BASE = "https://api.acleddata.com/acled/read"
ACLED_TOKEN_URL = "https://api.acleddata.com/token"

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
    page_delay: float = 1.0

    # Storage
    data_dir: Path = Path("data/raw/acled")
    ledger_path: Path = Path("provenance/acled/ingestion_ledger.jsonl")

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
            err_msg = (
                f"max_retries must be >= 1, got {self.max_retries}"
            )
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
        for et in self.event_types:
            if et not in ALL_EVENT_TYPES:
                err_msg = (
                    f"Unknown event type '{et}'. "
                    f"Valid: {ALL_EVENT_TYPES}"
                )
                logger.error(err_msg)
                raise ValueError(err_msg)


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


def fetch_paginated(
    config: AcledConfig,
    username: str,
    password: str,
    *,
    max_pages: int | None = None,
) -> list[dict]:
    """Fetch all ACLED events with limit/offset pagination.

    Args:
        config: Harvest configuration.
        username: ACLED username.
        password: ACLED password.
        max_pages: Stop after this many pages (None = fetch all).

    Returns:
        List of raw event dicts.
    """
    token_state = _acquire_token(
        username,
        password,
        config.token_url,
        config.timeout,
        config.max_retries,
    )

    all_events: list[dict] = []
    offset = 0
    page = 1

    while True:
        token_state = _ensure_token(
            token_state,
            username,
            password,
            config.token_url,
            config.timeout,
            config.max_retries,
        )

        headers = {
            "Authorization": f"Bearer {token_state.access_token}",
        }
        params: dict = {
            "event_date": (
                f"{config.start_year}-01-01"
                f"|{config.end_year}-12-31"
            ),
            "event_date_where": "BETWEEN",
            "limit": config.page_size,
            "offset": offset,
        }

        response = request_with_retry(
            config.api_url,
            headers=headers,
            params=params,
            max_retries=config.max_retries,
            timeout=config.timeout,
        )
        data = response.json()

        results = data.get("data", [])
        if not results:
            break

        all_events.extend(results)

        if page % _LOG_EVERY_N_PAGES == 0 or page == 1:
            logger.info(
                "Page %d: %d events so far (offset=%d)",
                page,
                len(all_events),
                offset,
            )

        if len(results) < config.page_size:
            break
        if max_pages is not None and page >= max_pages:
            logger.info(
                "Stopped after %d pages (max_pages limit)",
                max_pages,
            )
            break

        offset += config.page_size
        page += 1
        time.sleep(config.page_delay)

    logger.info("Fetched %d total ACLED events", len(all_events))
    return all_events


# ---- Orchestrator ----


def _snapshot_path(config: AcledConfig) -> Path:
    """Deterministic path for the raw event snapshot."""
    return (
        config.data_dir
        / f"acled_{config.start_year}_{config.end_year}.parquet"
    )


def fetch_acled(
    config: AcledConfig | None = None,
    *,
    username: str | None = None,
    password: str | None = None,
    force_refresh: bool = False,
) -> Path:
    """Fetch ACLED data: auth -> fetch -> validate -> store -> provenance.

    Args:
        config: Harvest configuration (defaults to full range).
        username: ACLED username (falls back to ACLED_USERNAME env var).
        password: ACLED password (falls back to ACLED_PASSWORD env var).
        force_refresh: If True, re-fetch even if snapshot exists.

    Returns:
        Path to the stored Parquet snapshot.
    """
    if config is None:
        config = AcledConfig()

    snap_path = _snapshot_path(config)

    if not force_refresh and snap_path.exists():
        previous = last_digest(config.ledger_path)
        if previous is not None:
            logger.info(
                "Snapshot exists and ledger has digest; skipping "
                "fetch (use force_refresh=True to override)"
            )
            return snap_path

    resolved_user, resolved_pass = get_acled_credentials(
        username, password
    )

    t0 = time.monotonic()
    events = fetch_paginated(
        config, resolved_user, resolved_pass
    )
    fetch_duration = time.monotonic() - t0

    validation = validate_events(
        events,
        REQUIRED_FIELDS,
        FIELD_TYPES,
        digest_fields=("event_id_cnty", "fatalities"),
    )

    min_date, max_date = date_range(events, field_name="event_date")

    base_entry = {
        "dataset": DATASET_ID,
        "start_year": config.start_year,
        "end_year": config.end_year,
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
        err_msg = f"Validation failed: {validation.errors}"
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
                "No revisions detected since previous snapshot"
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

    return snap_path


register_source("acled", fetch_acled)
