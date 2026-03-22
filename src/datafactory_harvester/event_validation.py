"""Source-agnostic event validation and snapshot comparison.

Provides structured result types and reusable validation/comparison
logic for any harvested event data. Source-specific schema definitions
(required fields, type mappings) are injected by the caller.

No knowledge of specific data sources (UCDP, ACLED, etc.).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import pyarrow.parquet as pq

from datafactory_provenance import compute_content_digest

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Outcome of validating a batch of raw events."""

    valid: bool
    n_events: int
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    schema_snapshot: dict[str, str] = field(default_factory=dict)
    content_digest: str = ""


@dataclass
class ComparisonResult:
    """Structured result from comparing two event snapshots."""

    has_previous: bool
    n_added: int = 0
    n_removed: int = 0
    n_revised: int = 0
    total_revision_magnitude: float = 0.0
    revised_events: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_events(
    events: list[dict],
    required_fields: set[str],
    field_types: dict[str, tuple[type, ...]],
    *,
    digest_fields: tuple[str, ...] = ("id", "best"),
) -> ValidationResult:
    """Validate raw events against a schema contract.

    Checks every event for required field presence and type correctness.
    Collects warnings for non-fatal issues (bound inconsistencies, etc.)
    without halting. Fatal schema violations are recorded as errors.

    Args:
        events: List of raw event dicts.
        required_fields: Field names that must be present.
        field_types: Mapping of field name to acceptable types.
        digest_fields: Fields to include in the content digest.

    Returns:
        ValidationResult; caller decides whether to halt or continue.
    """
    if not events:
        err_msg = "No events to validate."
        logger.error(err_msg)
        return ValidationResult(valid=False, n_events=0, errors=[err_msg])

    warnings: list[str] = []
    errors: list[str] = []

    # Schema snapshot from first event
    first = events[0]
    schema_snapshot = {k: type(v).__name__ for k, v in first.items()}

    # Check required fields on first event (fast fail)
    missing = required_fields - set(first.keys())
    if missing:
        err_msg = f"Required fields missing: {sorted(missing)}"
        logger.error(err_msg)
        errors.append(err_msg)
        return ValidationResult(
            valid=False,
            n_events=len(events),
            warnings=warnings,
            errors=errors,
            schema_snapshot=schema_snapshot,
        )

    # Check ID uniqueness (skip if ids are unhashable — type errors
    # will be caught by the per-event type check below)
    ids = [ev.get("id") for ev in events]
    try:
        unique_ids = set(ids)
        if len(unique_ids) != len(ids):
            n_dupes = len(ids) - len(unique_ids)
            warnings.append(
                f"Duplicate event IDs: {n_dupes} duplicates in {len(ids)} events"
            )
    except TypeError:
        warnings.append("Cannot check ID uniqueness: IDs contain unhashable types")

    # Validate types and values across all events
    negative_best = 0
    bound_violations = 0
    coord_violations = 0

    for i, ev in enumerate(events):
        ev_missing = required_fields - set(ev.keys())
        if ev_missing:
            errors.append(
                f"Event at index {i} (id={ev.get('id', '?')}) "
                f"missing fields: {sorted(ev_missing)}"
            )
            continue

        # Type checks on critical fields
        for field_name, expected_types in field_types.items():
            value = ev.get(field_name)
            if value is not None and not isinstance(value, expected_types):
                errors.append(
                    f"Event {ev.get('id', '?')}: field '{field_name}' "
                    f"is {type(value).__name__}, expected "
                    f"{'/'.join(t.__name__ for t in expected_types)}"
                )

        # Fatality bound checks (warnings, not errors)
        best = ev.get("best")
        high = ev.get("high")
        low = ev.get("low")

        if best is not None and isinstance(best, (int, float)):
            if best < 0:
                negative_best += 1
            if high is not None and isinstance(high, (int, float)) and best > high:
                bound_violations += 1
            if low is not None and isinstance(low, (int, float)) and low > best:
                bound_violations += 1

        # Coordinate range checks (warnings)
        lat = ev.get("latitude")
        lon = ev.get("longitude")
        if (
            lat is not None
            and isinstance(lat, (int, float))
            and not (-90 <= lat <= 90)
        ):
            coord_violations += 1
        if (
            lon is not None
            and isinstance(lon, (int, float))
            and not (-180 <= lon <= 180)
        ):
            coord_violations += 1

    if coord_violations > 0:
        warnings.append(
            f"Coordinate range violations on {coord_violations} "
            f"field values (lat outside [-90,90] or lon outside "
            f"[-180,180])"
        )
    if negative_best > 0:
        warnings.append(f"Negative 'best' values on {negative_best} events")
    if bound_violations > 0:
        warnings.append(
            f"Fatality bound violations (best>high or low>best) "
            f"on {bound_violations} events"
        )

    # Content digest from specified fields
    digest_data = sorted(
        tuple(ev.get(f, 0) for f in digest_fields) for ev in events
    )
    content_digest = compute_content_digest(
        json.dumps(digest_data, sort_keys=True).encode()
    )

    return ValidationResult(
        valid=len(errors) == 0,
        n_events=len(events),
        warnings=warnings,
        errors=errors,
        schema_snapshot=schema_snapshot,
        content_digest=content_digest,
    )


def compare_snapshots(
    old_path: Path,
    new_events: list[dict],
    *,
    id_field: str = "id",
    key_fields: tuple[str, ...] = ("best", "country_id", "date_start"),
) -> ComparisonResult:
    """Compare new events against a previous Parquet snapshot.

    Uses the id_field to match events across fetches. Detects added,
    removed, and revised events. Revision magnitude is computed on the
    first key_field (typically 'best' / fatality count).

    Args:
        old_path: Path to the previous Parquet snapshot.
        new_events: List of new event dicts.
        id_field: Field name used as the event identifier.
        key_fields: Fields to extract for comparison.

    Returns:
        ComparisonResult with structured diff data.
    """
    if not old_path.exists():
        return ComparisonResult(has_previous=False)

    old_table = pq.read_table(old_path)

    if id_field not in old_table.column_names:
        return ComparisonResult(
            has_previous=True,
            warnings=[
                f"Previous snapshot lacks '{id_field}' column; cannot compare"
            ],
        )

    # Build old lookup: id -> {key_field: value, ...}
    old_id_list = old_table.column(id_field).to_pylist()
    old_key_data: dict[str, list] = {}
    for kf in key_fields:
        if kf in old_table.column_names:
            old_key_data[kf] = old_table.column(kf).to_pylist()
        else:
            old_key_data[kf] = [None] * len(old_id_list)

    old_ids: set[int] = set()
    old_lookup: dict[int, dict] = {}
    for idx, oid in enumerate(old_id_list):
        if oid is not None:
            old_ids.add(oid)
            old_lookup[oid] = {kf: old_key_data[kf][idx] for kf in key_fields}

    # Build new lookup
    new_ids: set[int] = set()
    new_lookup: dict[int, dict] = {}
    for ev in new_events:
        eid = ev.get(id_field)
        if eid is not None:
            new_ids.add(eid)
            new_lookup[eid] = {kf: ev.get(kf) for kf in key_fields}

    # Compute diffs
    added = new_ids - old_ids
    removed = old_ids - new_ids
    common = old_ids & new_ids

    # Detect revised events (first key_field changed)
    magnitude_field = key_fields[0] if key_fields else None
    revised_events: list[dict] = []
    total_magnitude = 0.0

    if magnitude_field:
        for eid in common:
            old_val = old_lookup[eid].get(magnitude_field, 0) or 0
            new_val = new_lookup[eid].get(magnitude_field, 0) or 0
            if old_val != new_val:
                delta = new_val - old_val
                total_magnitude += abs(delta)
                revised_events.append({
                    id_field: eid,
                    f"old_{magnitude_field}": old_val,
                    f"new_{magnitude_field}": new_val,
                    "delta": delta,
                })

    revised_events.sort(key=lambda r: abs(r.get("delta", 0)), reverse=True)

    warnings = []
    if added:
        warnings.append(f"Revision: {len(added)} new events added")
    if removed:
        warnings.append(f"Revision: {len(removed)} events removed")
    if revised_events:
        warnings.append(
            f"Revision: {len(revised_events)} events with changed "
            f"'{magnitude_field}' values (total magnitude: "
            f"{total_magnitude:,.0f})"
        )

    return ComparisonResult(
        has_previous=True,
        n_added=len(added),
        n_removed=len(removed),
        n_revised=len(revised_events),
        total_revision_magnitude=total_magnitude,
        revised_events=revised_events,
        warnings=warnings,
    )
