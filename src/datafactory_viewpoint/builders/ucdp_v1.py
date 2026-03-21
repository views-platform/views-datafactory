"""UCDP viewpoint v1 — production-parity materialized view.

Reads the consolidated event store, applies survivorship rules
(annual wins) and temporal distribution (even split for summary
events), and writes a single Parquet with one row per event-month.

Targets parity with UCDP's .9 version (format YY.9.MM), a distinct
data source containing exclusive events beyond standard annual and
candidate releases. Note: full parity requires fetching .9 directly
— it cannot be reconstructed from annual + candidate alone.

Current strategy:
- Annual wins for months it covers
- Latest candidate for the trailing window
- Summary events (date_prec=5) distributed evenly
- Month assignment from date_end

Implements ADR-014 (viewpoints as derived views) and
ADR-015 (UCDP-specific rules).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from datafactory_provenance import (
    DIGEST_SCHEME,
    LEDGER_VERSION,
    append_ledger_entry,
    compute_content_digest,
)
from datafactory_viewpoint.builders import register_builder
from datafactory_viewpoint.survivorship import get_survivorship
from datafactory_viewpoint.temporal_distribution import (
    get_distribution,
)
from datafactory_viewpoint.viewpoint_config import ViewpointConfig
from datafactory_viewpoint.viewpoint_result import ViewpointResult

logger = logging.getLogger(__name__)

DATASET_ID = "ucdp_viewpoint"

# Columns added by consolidation that are not part of the viewpoint output
_CONSOLIDATION_METADATA = {"_source_type", "_source_version", "_ingested_at"}


def build_ucdp_v1(
    config: ViewpointConfig | None = None,
    *,
    consolidated_path: Path | None = None,
) -> ViewpointResult:
    """Build UCDP viewpoint v1 from a consolidated event store.

    Args:
        config: Full viewpoint configuration. If None, uses defaults
            with consolidated_path.
        consolidated_path: Shortcut — used only if config is None.

    Returns:
        ViewpointResult with record counts and output digest.

    Raises:
        FileNotFoundError: If the consolidated store doesn't exist.
        ValueError: If the store is empty or has invalid data.
    """
    if config is None:
        if consolidated_path is None:
            err_msg = (
                "Either config or consolidated_path must be provided"
            )
            logger.error(err_msg)
            raise ValueError(err_msg)
        config = ViewpointConfig(consolidated_path=consolidated_path)

    # Validate source exists
    if not config.consolidated_path.exists():
        err_msg = (
            f"Consolidated store not found: {config.consolidated_path}"
        )
        logger.error(err_msg)
        raise FileNotFoundError(err_msg)

    # Read consolidated store
    table = pq.read_table(config.consolidated_path)
    n_input = table.num_rows
    if n_input == 0:
        err_msg = "Consolidated store is empty"
        logger.error(err_msg)
        raise ValueError(err_msg)

    # Convert to list of dicts for processing
    col_dict = table.to_pydict()
    col_names = list(col_dict.keys())
    events = [
        {col: col_dict[col][i] for col in col_names}
        for i in range(n_input)
    ]

    logger.info(
        "Read consolidated store: %d events from %s",
        n_input, config.consolidated_path,
    )

    # Look up strategies
    survivorship_fn = get_survivorship(config.survivorship_strategy)
    distribution_fn = get_distribution(config.distribution_strategy)

    # Group by event id
    groups: dict[int, list[dict]] = defaultdict(list)
    for ev in events:
        groups[ev["id"]].append(ev)

    logger.info(
        "Grouped %d events into %d unique event IDs",
        n_input, len(groups),
    )

    # Apply survivorship: one winner per event id
    winners: list[dict] = []
    for versions in groups.values():
        winner = survivorship_fn(versions)
        winners.append(winner)

    logger.info(
        "Survivorship: %d groups → %d winners (strategy: %s)",
        len(groups), len(winners), config.survivorship_strategy,
    )

    # Apply temporal distribution: expand summary events
    output_rows: list[dict] = []
    n_summary = 0
    for winner in winners:
        distributed = distribution_fn(winner)
        if len(distributed) > 1:
            n_summary += 1
        output_rows.extend(distributed)

    logger.info(
        "Distribution: %d winners → %d rows "
        "(%d summary events expanded, strategy: %s)",
        len(winners), len(output_rows),
        n_summary, config.distribution_strategy,
    )

    # Strip consolidation metadata from output
    output_cols = [
        c for c in col_names if c not in _CONSOLIDATION_METADATA
    ]
    # Add date_month (always present in output)
    output_cols.append("date_month")

    # Build output table
    all_output_fields = sorted(
        {k for row in output_rows for k in row}
        - _CONSOLIDATION_METADATA
    )
    pa_columns = {}
    for field in all_output_fields:
        pa_columns[field] = pa.array(
            [row.get(field) for row in output_rows],
            from_pandas=True,
        )
    output_table = pa.table(pa_columns)

    # Write output
    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(output_table, config.output_path)

    output_digest = compute_content_digest(
        config.output_path.read_bytes()
    )

    # Record provenance
    append_ledger_entry(config.ledger_path, {
        "dataset": DATASET_ID,
        "version": config.version,
        "survivorship_strategy": config.survivorship_strategy,
        "distribution_strategy": config.distribution_strategy,
        "n_events_input": n_input,
        "n_events_output": len(output_rows),
        "n_summary_expanded": n_summary,
        "output_path": str(config.output_path),
        "output_digest": output_digest,
        "ledger_version": LEDGER_VERSION,
        "digest_algorithm": DIGEST_SCHEME,
    })

    logger.info(
        "Viewpoint %s built: %d → %d rows (digest: %s)",
        config.version, n_input, len(output_rows), output_digest,
    )

    return ViewpointResult(
        output_path=config.output_path,
        n_events_input=n_input,
        n_events_output=len(output_rows),
        n_summary_expanded=n_summary,
        output_digest=output_digest,
        version=config.version,
    )


# Auto-register
register_builder("ucdp_v1", build_ucdp_v1)
