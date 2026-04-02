"""Data harvesting framework with pluggable sources.

Pattern: config -> fetch -> validate -> store -> provenance.
Raw data stored unaltered. No transformation at fetch time.

Access specific sources via:
    from datafactory_harvester.sources.ucdp_annual import fetch_ucdp_annual

Or use the registry:
    from datafactory_harvester.sources import fetch_source
    fetch_source("ucdp_annual", config=...)
"""

from datafactory_harvester.event_validation import (
    ComparisonResult,
    ValidationResult,
    compare_snapshots,
    date_range,
    validate_events,
)
from datafactory_harvester.snapshot_storage import archive_snapshot, save_event_snapshot
from datafactory_harvester.sources import fetch_source, list_sources, register_source

__all__ = [
    "ValidationResult",
    "ComparisonResult",
    "validate_events",
    "compare_snapshots",
    "date_range",
    "save_event_snapshot",
    "archive_snapshot",
    "register_source",
    "fetch_source",
    "list_sources",
]
