"""ACLED (Armed Conflict Location & Event Data) source.

Fetches event-level conflict and protest data from the ACLED API.
API docs: https://apidocs.acleddata.com/

Authentication: OAuth2 password grant (ADR-026). Each user must
authenticate with their own credentials — credential sharing is
prohibited by ACLED's EULA.

Source-specific concerns: OAuth token lifecycle, event type taxonomy,
daily granularity, cursor-based pagination. Uses the shared harvester
skeleton (validation, storage, provenance).

Pagination moved from offset (`&page=N`) to cursor (`&cursor=X`) in
October 2026, because ACLED removed the offset method on 2026-10-27.
See `fetch_paginated()` below and #487.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import requests

from datafactory_harvester.event_validation import (
    ComparisonResult,
    compare_snapshots,
    date_range,
    validate_dgp_assumptions,
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
from datafactory_http import redact_url, request_with_retry
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

# ---- DGP assumption checks (C-257) ----


def _check_fatality_non_negative(event: dict) -> str | None:
    """Fatalities must be >= 0."""
    val = event.get("fatalities")
    if val is not None:
        try:
            if float(val) < 0:
                return f"Negative fatalities: {val}"
        except (TypeError, ValueError):
            pass
    return None


def _check_known_event_type(event: dict) -> str | None:
    """Event type must be in ALL_EVENT_TYPES."""
    et = event.get("event_type")
    if et is not None and et not in ALL_EVENT_TYPES:
        return f"Unknown event_type: {et!r}"
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


ACLED_DGP_CHECKS: tuple[
    Callable[[dict], str | None], ...
] = (
    _check_fatality_non_negative,
    _check_known_event_type,
    _check_coordinate_bounds,
)


# ---- Config ----


@dataclass(frozen=True)
class AcledConfig:
    """Configuration for fetching ACLED event data."""

    start_year: int = 1997
    end_year: int = 0

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
        if self.end_year == 0:
            object.__setattr__(
                self, "end_year",
                datetime.datetime.now(tz=datetime.UTC).year,
            )
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
    """Fetch all ACLED events with cursor-based pagination.

    ACLED deprecated offset (``&page=N``) pagination on 2026-10-27 (#487).
    The walk sends ``&cursor=X`` starting at 0 and advances to the
    ``next_cursor`` each response carries. ``next_cursor: null`` is the
    ONLY authoritative end of the series -- a short page is not, which is
    why the old ``len(results) < page_size`` break is gone. The cursor is
    an opaque integer and 0 is a legitimate value, so termination tests
    ``is None`` and never falsiness.

    Args:
        config: Harvest configuration.
        username: ACLED username.
        password: ACLED password.
        max_pages: Stop after this many pages (None = fetch all).
        _token_state: Pre-acquired token (avoids re-auth per year).

    Returns:
        List of raw event dicts.

    Raises:
        ValueError: If a response omits ``next_cursor``, or returns no
            events while the cursor is still live. Both mean the series
            boundary cannot be determined, and guessing it would truncate
            a harvest silently (ADR-011).
    """
    token_state = _token_state or _acquire_token(
        username,
        password,
        config.token_url,
        config.timeout,
        config.max_retries,
    )

    all_events: list[dict] = []
    cursor: int | str = 0
    # Seeded with the starting cursor: a response echoing 0 back is
    # already a non-advancing walk. See the progress guard below.
    seen_cursors: set[int | str] = {0}
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
            "cursor": cursor,
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

        # The envelope must declare whether more pages exist. Without
        # next_cursor there is no way to tell "series complete" from
        # "page boundary", and ACLED reports count/total_count as null
        # (C-153), so there is no second signal to fall back on.
        if "next_cursor" not in data:
            err_msg = (
                "ACLED response missing 'next_cursor'. Cursor pagination "
                "cannot determine the end of the series without it, and "
                "guessing would truncate the harvest silently. "
                f"Response keys: {sorted(data.keys())}"
            )
            logger.error(err_msg)
            raise ValueError(err_msg)

        next_cursor = data["next_cursor"]

        if not results and next_cursor is not None:
            err_msg = (
                "ACLED returned no events while the cursor is still live "
                f"(page {page}, cursor {cursor!r}, "
                f"{len(all_events)} events so far). Refusing both to "
                "continue and to treat this as the end of the series. "
                "MOST LIKELY BENIGN CAUSE: the slice holds an exact "
                f"multiple of limit={config.page_size}, so the last "
                "full page was followed by an empty one. Check "
                f"{len(all_events)} % {config.page_size} == 0 before "
                "assuming a provider fault."
            )
            logger.error(err_msg)
            raise ValueError(err_msg)

        all_events.extend(results)

        if page % _LOG_EVERY_N_PAGES == 0 or page == 1:
            logger.info(
                "Page %d: %d events fetched so far",
                page,
                len(all_events),
            )

        if next_cursor is None:
            break

        # Checked before the progress guard: if the walk is stopping at
        # the cap anyway, the cursor's value is irrelevant, and raising
        # on it would make `harvest_acled.py --proof` report a failure
        # for a credential that plainly works.
        if max_pages is not None and page >= max_pages:
            logger.info(
                "Stopped after %d pages (max_pages limit)",
                max_pages,
            )
            break

        # The cursor has to be hashable to be tracked, and a type
        # change is the same class of provider drift as the missing key
        # guarded above — so it gets the same named error rather than a
        # bare TypeError out of the set lookup below.
        if not isinstance(next_cursor, str | int):
            err_msg = (
                "ACLED returned a non-scalar 'next_cursor' of type "
                f"{type(next_cursor).__name__} (page {page}): "
                f"{next_cursor!r}. Cursor pagination needs a scalar "
                "token to detect a stalled walk."
            )
            logger.error(err_msg)
            raise ValueError(err_msg)

        # The SERVER must advance the cursor or the walk cannot make
        # progress. Under offset pagination `page += 1` guaranteed
        # forward motion; under cursor pagination only ACLED can, so a
        # repeated cursor would re-request the same page indefinitely —
        # accumulating duplicates one request per `page_delay` against
        # a rate-limited API, inside an unattended monthly cron. A set
        # rather than a `!=` check because it also catches a longer
        # cycle, and 80 integers is nothing.
        if next_cursor in seen_cursors:
            err_msg = (
                f"ACLED returned cursor {next_cursor!r} a second time "
                f"(page {page}, {len(all_events)} events so far). The "
                "walk is not advancing, so continuing would re-fetch "
                "the same page indefinitely."
            )
            logger.error(err_msg)
            raise ValueError(err_msg)
        seen_cursors.add(next_cursor)

        cursor = next_cursor
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
    """Check if a year's snapshot exists with a matching ledger digest.

    The current year is never considered cached because ACLED publishes
    new events biweekly — the local snapshot is always stale.
    """
    if year >= datetime.datetime.now(tz=datetime.UTC).year:
        return False
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


def _append_failed_fetch_entry(
    config: AcledConfig,
    year: int,
    exc: BaseException,
) -> None:
    """Record ADR-011's failed-harvest entry for a year that never fetched.

    ADR-011 consequence #2 requires a provenance ledger entry with
    ``outcome: "failed"`` when a harvest fails. The validation path below
    has always written one; the fetch path never did. So when the monthly
    cron hit a 429 mid-walk on 2026-10-21, ``ingestion_ledger.jsonl``
    stayed silent and the only artifact naming the cause was
    ``logs/refresh.log`` — mode ``rw-r-----``, owner ``views-deploy``.
    Diagnosing one line took about an hour and a ``sudo`` (#513).

    The entry is deliberately thin. ``n_events``, ``content_digest``,
    ``min_date`` and ``max_date`` cannot be filled in: nothing was
    fetched. What an operator needs at 02:00 is which year, and why.

    ``error`` is singular and a string, where the validation entries carry
    a plural ``errors`` list. That is the distinction, not an
    inconsistency: those hold a list of per-field validation problems,
    this holds one exception. Nothing reads either key programmatically.

    Credential masking is applied HERE rather than trusted from upstream.
    It is belt-and-braces today — every ACLED request goes through
    ``request_with_retry``, whose messages are already redacted, and ACLED
    sends its password in a POST body and its token in a header, never in
    a query string. It is applied anyway because this function writes to a
    world-readable file, which makes it a publication rather than a log
    line, and C-322 was a credential reaching disk through exactly this
    carrier: a ``requests`` exception message. Masking at the write means
    an error path added later, one that never touches the HTTP layer,
    cannot leak through this one.

    Never raises. Both callers invoke this from inside ``except`` before a
    bare ``raise``, so an exception escaping here would replace the fetch
    error with a write error and the real reason would survive only in
    ``__context__``, which nothing prints — no ledger entry AND no reason,
    which is worse than the gap this function was added to close. The
    scenario is not hypothetical: ``append_ledger_entry`` re-raises
    ``OSError`` (``digests_and_ledgers.py``), and a full disk is a
    plausible *shared* cause of the harvest failing in the first place,
    with a 37 GB grid and a 3.1 GB zarr store on the same host. Broad
    rather than ``OSError`` alone because a best-effort recorder on an
    error path has nothing to gain from being selective. The failure is
    logged, so ``refresh.log`` still says the ledger could not be written.
    Same decision as ``scripts/export_zarr.py``'s ``finally`` block.
    """
    try:
        append_ledger_entry(config.ledger_path, {
            "dataset": DATASET_ID,
            "version": f"{year}_{year}",
            "start_year": year,
            "end_year": year,
            "outcome": "failed",
            "error": redact_url(f"{type(exc).__name__}: {exc}"),
            "ledger_version": LEDGER_VERSION,
            "digest_algorithm": DIGEST_SCHEME,
        })
    except Exception:
        logger.exception(
            "Could not write the failed-harvest ledger entry for year "
            "%d to %s — the fetch error below is the one that matters",
            year,
            config.ledger_path,
        )


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
    try:
        events = fetch_paginated(
            year_config,
            resolved_user,
            resolved_pass,
            _token_state=token_state,
        )
    except Exception as exc:
        # Broad on purpose, and it re-raises rather than handling.
        # fetch_paginated raises requests exceptions for transport and
        # status faults AND ValueError for the cursor guards (a repeated
        # cursor, a non-scalar cursor, an empty page with a live cursor).
        # An operator needs the ledger to name any of those; narrowing to
        # RequestException would record the 429 that prompted this and
        # silently drop the pagination faults, which are the harder ones
        # to diagnose from a step number alone.
        logger.error("ACLED fetch failed for year %d", year)
        _append_failed_fetch_entry(config, year, exc)
        raise
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

    validate_dgp_assumptions(
        events, ACLED_DGP_CHECKS, source_name="ACLED",
    )

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

        # Guarded for the same reason the fetch below is: a 429 or a
        # transport fault on the token POST is a failed ACLED harvest
        # that the ledger would otherwise not record. Same provider,
        # same rate limiter, and the year is in hand here — covering the
        # walk but not the authentication in front of it would draw the
        # line in an arbitrary place.
        try:
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
        except Exception as exc:
            logger.error(
                "ACLED authentication failed before year %d", year,
            )
            _append_failed_fetch_entry(config, year, exc)
            raise

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
