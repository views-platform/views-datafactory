"""ACLED viewpoint v1 — daily events aggregated to monthly.

Reads the ACLED consolidated event store, assigns each daily event
to its calendar month (date_month), optionally filters by event type,
and writes a Parquet with one row per event.

No survivorship needed (single source type, no overlapping vintages).
No temporal distribution needed (daily events map 1:1 to months).

Implements ADR-014 (viewpoints as derived views).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from datafactory_provenance import (
    DIGEST_SCHEME,
    LEDGER_VERSION,
    append_ledger_entry,
    compute_file_digest,
)
from datafactory_viewpoint.builders import register_builder
from datafactory_viewpoint.viewpoint_result import ViewpointResult

logger = logging.getLogger(__name__)

DATASET_ID = "acled_viewpoint"

REQUIRED_CONSOLIDATED_FIELDS: set[str] = {
    "event_id_cnty",
    "event_date",
    "event_type",
    "latitude",
    "longitude",
    "fatalities",
}

PRODUCED_FIELDS: tuple[str, ...] = ("date_month",)

STRIPPED_FIELDS: set[str] = {
    "_source_type",
    "_source_version",
    "_ingested_at",
    "_harvest_digest",
    "_harvest_timestamp",
}


@dataclass(frozen=True)
class AcledViewpointConfig:
    """Configuration for building an ACLED viewpoint.

    Simpler than the UCDP ViewpointConfig — no survivorship or
    distribution strategies needed.
    """

    consolidated_path: Path

    output_path: Path = Path(
        "data/viewpoint/acled_v1.parquet"
    )
    ledger_path: Path = Path(
        "provenance/viewpoint/acled_v1_ledger.jsonl"
    )

    event_type_filter: tuple[str, ...] | None = None

    version: str = "acled_v1"

    def __post_init__(self) -> None:
        if not self.version:
            err_msg = "version must be non-empty"
            logger.error(err_msg)
            raise ValueError(err_msg)

    @classmethod
    def from_shortcuts(
        cls, *, consolidated_path: Path,
    ) -> AcledViewpointConfig:
        """Construct config from minimal shortcut arguments."""
        return cls(consolidated_path=consolidated_path)


def _assign_date_month(event_date: str) -> str:
    """Extract YYYY-MM from a daily event_date string."""
    return event_date[:7]


def build_acled_v1(
    config: AcledViewpointConfig,
) -> ViewpointResult:
    """Build ACLED viewpoint v1 from a consolidated event store.

    Returns:
        ViewpointResult with record counts and output digest.
    """
    if not config.consolidated_path.exists():
        err_msg = (
            f"Consolidated store not found: "
            f"{config.consolidated_path}"
        )
        logger.error(err_msg)
        raise FileNotFoundError(err_msg)

    schema = pq.read_schema(config.consolidated_path)
    missing = REQUIRED_CONSOLIDATED_FIELDS - set(schema.names)
    if missing:
        err_msg = (
            f"Consolidated store missing required fields: "
            f"{sorted(missing)}"
        )
        logger.error(err_msg)
        raise ValueError(err_msg)

    skip_cols = STRIPPED_FIELDS - REQUIRED_CONSOLIDATED_FIELDS
    keep_cols = [
        c for c in schema.names
        if c not in skip_cols
    ]
    table = pq.read_table(
        config.consolidated_path, columns=keep_cols,
    )
    n_input = table.num_rows
    if n_input == 0:
        err_msg = "Consolidated store is empty"
        logger.error(err_msg)
        raise ValueError(err_msg)

    logger.info(
        "Read ACLED consolidated store: %d events from %s",
        n_input,
        config.consolidated_path,
    )

    n_filtered = 0

    if config.event_type_filter is not None:
        filter_set = pa.array(config.event_type_filter)
        mask = pc.is_in(
            table.column("event_type"), filter_set
        )
        n_before = table.num_rows
        table = table.filter(mask)
        n_filtered = n_before - table.num_rows
        logger.info(
            "Event type filter: %d → %d events (%d filtered)",
            n_before,
            table.num_rows,
            n_filtered,
        )

    event_dates = table.column("event_date").to_pylist()
    date_months = [_assign_date_month(d) for d in event_dates]
    table = table.append_column(
        "date_month",
        pa.array(date_months, type=pa.string()),
    )

    n_output = table.num_rows

    if n_input != n_output + n_filtered:
        raise RuntimeError(
            f"Count conservation violation: "
            f"input ({n_input}) != "
            f"output ({n_output}) + filtered ({n_filtered})"
        )

    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, config.output_path)

    output_digest = compute_file_digest(config.output_path)

    append_ledger_entry(config.ledger_path, {
        "dataset": DATASET_ID,
        "version": config.version,
        "event_type_filter": config.event_type_filter,
        "n_events_input": n_input,
        "n_events_output": n_output,
        "n_filtered": n_filtered,
        "output_path": str(config.output_path),
        "output_digest": output_digest,
        "ledger_version": LEDGER_VERSION,
        "digest_algorithm": DIGEST_SCHEME,
    })

    logger.info(
        "ACLED viewpoint %s built: %d → %d rows (digest: %s)",
        config.version,
        n_input,
        n_output,
        output_digest,
    )

    return ViewpointResult(
        output_path=config.output_path,
        n_events_input=n_input,
        n_events_output=n_output,
        n_summary_expanded=0,
        n_filtered=n_filtered,
        output_digest=output_digest,
        version=config.version,
    )


register_builder("acled_v1", build_acled_v1)
