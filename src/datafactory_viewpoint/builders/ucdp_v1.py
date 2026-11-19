"""UCDP viewpoint v1 — production-parity materialized view.

Reads the consolidated event store, applies configurable
survivorship rules, temporal and spatial distribution, then
writes a single Parquet with one row per event-month-cell.

Processing order:
1. Stale-version filtering (configurable via filter_stale_versions)
2. Survivorship — one winner per event id (strategy via config)
3. Temporal distribution — expand summary events (strategy via
   config, with optional per-source-type overrides)
4. Spatial distribution — expand imprecise events across polygon
   cells (ADR-049, strategy via config)
5. Filtering — priogrid_gid, type_of_violence, where_prec
6. Output — Parquet with date_month column, metadata stripped

Non-configurable invariants documented in ADR-023.
Implements ADR-014 (viewpoints as derived views),
ADR-015 (UCDP-specific rules), and
ADR-049 (spatial distribution of imprecise events).
"""

from __future__ import annotations

import logging

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
from datafactory_viewpoint.spatial_distribution import (
    get_spatial_distribution,
)
from datafactory_viewpoint.spatial_weights import (
    build_spatial_weight_map,
)
from datafactory_viewpoint.survivorship import get_survivorship
from datafactory_viewpoint.temporal_distribution import (
    TemporalStrategy,
    get_distribution,
)
from datafactory_viewpoint.temporal_weights import (
    build_temporal_weight_map,
)
from datafactory_viewpoint.viewpoint_config import ViewpointConfig
from datafactory_viewpoint.viewpoint_result import ViewpointResult

logger = logging.getLogger(__name__)

DATASET_ID = "ucdp_viewpoint"

# ---- Boundary declarations (ADR-009) ----
# What this layer REQUIRES from the consolidated store
REQUIRED_CONSOLIDATED_FIELDS: set[str] = {
    "id", "_source_type", "_source_version",
    "date_start", "date_end", "date_prec",
    "best", "low", "high",
    "priogrid_gid", "where_prec",
}

# What this layer PRODUCES (columns added to output)
PRODUCED_FIELDS: tuple[str, ...] = ("date_month",)

# What this layer STRIPS (consolidation metadata not in output)
STRIPPED_FIELDS: set[str] = {
    "_source_type", "_source_version", "_ingested_at",
    "_harvest_digest", "_harvest_timestamp",
}


def _passes_filters(
    row: dict, config: ViewpointConfig,
) -> bool:
    """Check if an event row passes all configured filters."""
    if (
        config.min_priogrid_gid is not None
        and (row.get("priogrid_gid") or 0) < config.min_priogrid_gid
    ):
        return False
    if (
        config.max_type_of_violence is not None
        and (row.get("type_of_violence") or 0)
        > config.max_type_of_violence
    ):
        return False
    return not (
        config.exclude_where_prec
        and not row.get("_spatial_distributed")
        and row.get("where_prec") in config.exclude_where_prec
    )


def build_ucdp_v1(
    config: ViewpointConfig,
) -> ViewpointResult:
    """Build UCDP viewpoint v1 from a consolidated event store.

    Uses sorted-group processing to avoid materializing all events
    as Python dicts simultaneously. Peak memory is ~1 GB instead
    of ~4 GB for 2.3M events.

    Returns:
        ViewpointResult with record counts and output digest.

    Raises:
        FileNotFoundError: If the consolidated store doesn't exist.
        ValueError: If the store is empty or has invalid data.
    """
    # Validate source exists
    if not config.consolidated_path.exists():
        err_msg = (
            f"Consolidated store not found: "
            f"{config.consolidated_path}"
        )
        logger.error(err_msg)
        raise FileNotFoundError(err_msg)

    # Read consolidated store, skipping metadata columns not
    # needed for processing (keep _source_type/_source_version
    # for survivorship, skip _ingested_at/_harvest_* metadata).
    schema = pq.read_schema(config.consolidated_path)
    skip_cols = STRIPPED_FIELDS - REQUIRED_CONSOLIDATED_FIELDS
    read_cols = [
        c for c in schema.names if c not in skip_cols
    ]
    table = pq.read_table(
        config.consolidated_path, columns=read_cols,
    )
    n_read = table.num_rows
    if n_read == 0:
        err_msg = "Consolidated store is empty"
        logger.error(err_msg)
        raise ValueError(err_msg)

    logger.info(
        "Read consolidated store: %d events from %s",
        n_read, config.consolidated_path,
    )
    n_stale = 0

    # Filter stale non-annual versions (ADR-023).
    # Controlled by config.filter_stale_versions.
    if config.filter_stale_versions:
        # VIEWSER's GedLoader processes sources in a specific order:
        # 1. Annual is loaded first (authoritative, curated).
        # 2. .9 monthly release overwrites the trailing 12 months.
        # 3. Candidate updates individual months.
        #
        # For months covered by the annual, ONLY annual events
        # exist in VIEWSER — candidate and .9 events for those
        # months are replaced. We replicate this by:
        #   a0) Letting the latest annual release supersede older
        #       ones for the span it covers (#595)
        #   a) Determining the annual's temporal coverage
        #   b) Dropping candidate/.9 rows whose event id doesn't
        #      appear in the annual
        #   c) Keeping only the latest .9 version
        source_types = table.column("_source_type")
        source_versions = table.column("_source_version")
        n_before = table.num_rows

        from datafactory_viewpoint.survivorship import _parse_version

        # (a0) The latest annual release supersedes older ones
        # for the span it covers (#595).
        #
        # UCDP does not only revise events between annual
        # releases — it deletes and merges them. The store is
        # append-only by design (ADR-013), so an event dropped in
        # v26.1 still carries its v25.1 row here. Without this
        # step that row is annual, so (b) keeps it
        # unconditionally, (c) never looks at annual, and
        # survivorship cannot help because the id has no
        # competing row. The deleted event gets republished.
        #
        # This runs BEFORE (a) deliberately: a .9 or candidate
        # row for a deleted event is then dropped with it,
        # because its id is no longer among annual_ids.
        #
        # Supersession is bounded by the latest release's own
        # coverage, and that bound is UPPER-ONLY: an older row
        # whose event ends after the latest release's last event
        # survives, because the latest release says nothing about
        # that period and cannot be read as having withdrawn
        # anything there. Today it selects nothing (v26.1 spans
        # 1989-2025, v25.1 spans 1989-2024), but a release ending
        # earlier than its predecessor must not silently delete
        # the trailing years.
        #
        # There is deliberately NO lower bound, and a release
        # whose coverage STARTS later than its predecessor's would
        # therefore delete the earlier history (#598). The bound
        # cannot be fixed here: max(date_end) is a sound proxy for
        # where coverage ends because a release is dense up to its
        # cutoff, but min(date_start) is not a proxy for where
        # coverage begins — in a sparse store it is just the
        # earliest event that happens to be present. The declared
        # span is in the snapshot filename and is discarded by
        # _ANNUAL_PATTERN during consolidation, so closing the gap
        # means carrying it into the store. Every UCDP annual
        # release so far starts at 1989.
        #
        # When the upper clause does select rows, (a)'s
        # annual_cutoff and annual_ids then span two releases.
        # That is correct, because the two releases legitimately
        # cover different periods.
        annual_mask = pc.equal(source_types, "annual")
        annual_versions = pc.filter(source_versions, annual_mask)
        distinct_annual = annual_versions.unique().to_pylist()

        # Refuse to supersede unless the annual versions are
        # totally ordered by _parse_version. Two ways they are not:
        #
        #  - a non-numeric string, which _parse_version maps to
        #    (0,). In (c) that only loses a preference; here it
        #    would elect the wrong release as latest and delete
        #    the real one.
        #  - two distinct strings that parse to the SAME tuple,
        #    e.g. "26.1" and "26.01" both give (26, 1), because
        #    _ANNUAL_PATTERN captures [\d.]+ from the filename.
        #    max() would then keep whichever unique() happened to
        #    return first, making the outcome depend on row order
        #    in the store.
        #
        # Either way the ordering is not trustworthy, so overcount
        # visibly rather than delete silently.
        unorderable = sorted(
            v
            for v in distinct_annual
            if not all(p.isdigit() for p in v.split("."))
        )
        parsed: dict[tuple[int, ...], list[str]] = {}
        for v in distinct_annual:
            parsed.setdefault(_parse_version(v), []).append(v)
        ambiguous = sorted(
            v
            for versions in parsed.values()
            if len(versions) > 1
            for v in versions
        )
        if unorderable or ambiguous:
            logger.warning(
                "Annual versions are not totally ordered "
                "(non-numeric: %s; ambiguous: %s); refusing to "
                "supersede any annual release. Superseded events "
                "may remain in the output.",
                unorderable,
                ambiguous,
            )
        elif len(distinct_annual) > 1:
            latest_annual = max(distinct_annual, key=_parse_version)
            latest_mask = pc.and_(
                annual_mask,
                pc.equal(source_versions, latest_annual),
            )
            latest_end = pc.max(
                pc.filter(table.column("date_end"), latest_mask)
            )
            keep = pc.or_(
                pc.not_equal(source_types, "annual"),
                pc.or_(
                    pc.equal(source_versions, latest_annual),
                    pc.greater(
                        table.column("date_end"), latest_end,
                    ),
                ),
            )
            n_annual_before = table.num_rows
            table = table.filter(keep)
            superseded = sorted(
                set(distinct_annual) - {latest_annual}
            )
            logger.info(
                "Annual %s supersedes %s through %s: "
                "dropped %d rows",
                latest_annual,
                superseded,
                latest_end.as_py(),
                n_annual_before - table.num_rows,
            )
            source_types = table.column("_source_type")
            source_versions = table.column("_source_version")

        # (a) Find annual coverage boundary
        annual_mask = pc.equal(source_types, "annual")
        annual_dates = pc.filter(
            table.column("date_end"), annual_mask,
        )
        if len(annual_dates) > 0:
            annual_cutoff = max(annual_dates.to_pylist())
            annual_ids = set(
                pc.filter(
                    table.column("id"), annual_mask,
                ).to_pylist()
            )
            logger.info(
                "Annual covers through %s (%d events)",
                annual_cutoff, len(annual_ids),
            )

            # (b) Drop non-annual rows for events NOT in
            # annual within the annual coverage period
            ids_col = table.column("id")
            dates_col = table.column("date_end")
            is_annual = annual_mask
            in_annual_ids = pc.is_in(
                ids_col, pa.array(sorted(annual_ids)),
            )
            in_annual_period = pc.less_equal(
                dates_col, pa.scalar(annual_cutoff),
            )
            keep = pc.or_(
                is_annual,
                pc.or_(
                    in_annual_ids,
                    pc.invert(in_annual_period),
                ),
            )
            table = table.filter(keep)

        # (c) For .9 sources: keep only the latest version
        source_types = table.column("_source_type")
        source_versions = table.column("_source_version")
        dot9_mask = pc.equal(source_types, "dot9")
        dot9_versions = pc.filter(source_versions, dot9_mask)
        if len(dot9_versions) > 0:
            latest_dot9 = max(
                dot9_versions.unique().to_pylist(),
                key=_parse_version,
            )
            keep = pc.or_(
                pc.not_equal(source_types, "dot9"),
                pc.equal(source_versions, latest_dot9),
            )
            table = table.filter(keep)

        n_stale = n_before - table.num_rows
        if n_stale > 0:
            logger.info(
                "Filtered %d stale rows (%d remain)",
                n_stale, table.num_rows,
            )
    else:
        logger.info(
            "Stale-version filtering disabled by config"
        )

    # Update count after optional stale filtering
    n_input = table.num_rows

    if n_read != n_input + n_stale:
        raise RuntimeError(
            f"Count conservation violation at stale filtering: "
            f"read ({n_read}) != "
            f"input ({n_input}) + stale ({n_stale})"
        )

    # Look up strategies
    survivorship_fn = get_survivorship(config.survivorship_strategy)
    distribution_fn = get_distribution(config.distribution_strategy)
    spatial_dist_fn = get_spatial_distribution(
        config.spatial_distribution_strategy,
    )

    # Pre-resolve source-distribution overrides
    source_dist_fns: dict[str, TemporalStrategy] | None = None
    if config.source_distribution_map is not None:
        source_dist_fns = {
            src: get_distribution(strat)
            for src, strat in config.source_distribution_map.items()
        }

    # Build spatial weight map (if distributing)
    weight_map = None
    if config.spatial_distribution_strategy != "passthrough":
        weight_map = build_spatial_weight_map(
            table,
            config.gaul1_crosswalk_path,
            config.gaul0_crosswalk_path,
        )

    # Build the monthly activity indicator only if some temporal strategy
    # actually wants one. Scanning the table to build an indicator nothing
    # reads would be pure cost, and a strategy that silently got None
    # would fall back to uniform without saying so.
    temporal_strategies = {config.distribution_strategy}
    if config.source_distribution_map is not None:
        temporal_strategies |= set(config.source_distribution_map.values())
    temporal_weight_map = None
    if "activity_weighted" in temporal_strategies:
        temporal_weight_map = build_temporal_weight_map(table)

    # Sort by event id for grouped processing
    table = table.sort_by("id")
    col_names = table.column_names

    # Get id column as Python list for group boundary detection
    ids = table.column("id").to_pylist()

    # Prepare output columns (streaming accumulation)
    output_col_names = [
        c for c in col_names if c not in STRIPPED_FIELDS
    ]
    output_col_names.append("date_month")
    output_columns: dict[str, list] = {
        col: [] for col in output_col_names
    }

    n_groups = 0
    n_summary = 0
    n_filtered = 0
    n_spatially_distributed = 0
    n_spatial_cells_created = 0
    n_excluded_where_prec = 0
    n_passthrough_where_prec = 0

    # ADR-053 Validation & Monitoring asks for these on every build: how
    # many events the temporal stage allocated, which cascade level
    # supplied each one's weights, and how many fell through to uniform.
    # The fallback count is the one worth watching -- activity weighting's
    # whole claim is that a conflict's own observed monthly pattern is a
    # better prior than a flat one, and an event that falls back got no
    # such pattern. If that share climbs, the claim is weakening on data
    # nobody re-examined.
    n_temporally_distributed = 0
    temporal_weight_key_counts: dict[str, int] = {}

    # Process groups: walk sorted id column, slice per group
    i = 0
    while i < n_input:
        # Find end of current group (same event id)
        current_id = ids[i]
        j = i + 1
        while j < n_input and ids[j] == current_id:
            j += 1

        # Extract group as list of dicts (small: typically 1-5)
        group_slice = table.slice(i, j - i)
        group_dict = group_slice.to_pydict()
        group_events = [
            {col: group_dict[col][k] for col in col_names}
            for k in range(j - i)
        ]

        # Survivorship: pick winner from group
        winner = survivorship_fn(group_events)
        n_groups += 1

        # Distribution: expand summary events
        # Use per-source override if configured, else default
        if source_dist_fns is not None:
            src_type = winner.get("_source_type", "")
            fn = source_dist_fns.get(src_type, distribution_fn)
        else:
            fn = distribution_fn
        distributed = fn(winner, temporal_weight_map)
        if len(distributed) > 1:
            n_summary += 1

        # Every row from one event carries the same temporal annotations,
        # so the first row answers for the event. ``activity_weighted``
        # sets ``_temporal_weight_key`` to the cascade level it used, and
        # leaves it absent when it fell back to ``uniform_span`` -- which
        # is why absence is bucketed explicitly rather than ignored.
        if distributed and distributed[0].get("_temporal_distributed"):
            n_temporally_distributed += 1
            bucket = (
                distributed[0].get("_temporal_weight_key")
                or "uniform_fallback"
            )
            temporal_weight_key_counts[bucket] = (
                temporal_weight_key_counts.get(bucket, 0) + 1
            )

        # Spatial distribution: expand imprecise events
        if weight_map is not None:
            spatially_expanded: list[dict] = []
            event_was_distributed = False
            for row in distributed:
                expanded = spatial_dist_fn(row, weight_map)
                if len(expanded) > 1:
                    event_was_distributed = True
                    n_spatial_cells_created += len(expanded)
                spatially_expanded.extend(expanded)
            if event_was_distributed:
                n_spatially_distributed += 1
            distributed = spatially_expanded

        # Count passthrough events (where_prec >= 4 but not distributed)
        for row in distributed:
            if (
                row.get("where_prec", 1) >= 4
                and not row.get("_spatial_distributed")
            ):
                n_passthrough_where_prec += 1

        # Filter + append to output columns
        for row in distributed:
            if not _passes_filters(row, config):
                n_filtered += 1
                if (
                    config.exclude_where_prec
                    and not row.get("_spatial_distributed")
                    and row.get("where_prec")
                    in config.exclude_where_prec
                ):
                    n_excluded_where_prec += 1
                continue
            for col in output_col_names:
                output_columns[col].append(row.get(col))

        i = j

    logger.info(
        "Processed %d groups: %d summary expanded, "
        "%d temporally distributed (weights: %s), "
        "%d spatially distributed (%d cells), "
        "%d passthrough where_prec, %d excluded where_prec, "
        "%d filtered, %d output rows",
        n_groups, n_summary,
        n_temporally_distributed,
        ", ".join(
            f"{k}={v}"
            for k, v in sorted(temporal_weight_key_counts.items())
        ) or "none",
        n_spatially_distributed, n_spatial_cells_created,
        n_passthrough_where_prec, n_excluded_where_prec,
        n_filtered, len(output_columns["date_month"]),
    )

    # Build output table from accumulated columns
    pa_columns = {
        col: pa.array(vals, from_pandas=True)
        for col, vals in output_columns.items()
    }
    output_table = pa.table(pa_columns)

    # Write output
    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(output_table, config.output_path)

    output_digest = compute_file_digest(config.output_path)

    n_output = len(output_columns["date_month"])
    n_survivorship_discarded = n_input - n_groups

    # Record provenance
    append_ledger_entry(config.ledger_path, {
        "dataset": DATASET_ID,
        "version": config.version,
        "survivorship_strategy": config.survivorship_strategy,
        "distribution_strategy": config.distribution_strategy,
        "spatial_distribution_strategy": (
            config.spatial_distribution_strategy
        ),
        # None while every strategy is deterministic. Recorded regardless
        # so the reproducibility contract of ADR-014 Principle 3 is in the
        # ledger before the first stochastic strategy needs it.
        "seed": config.seed,
        "temporal_activity_pool_events": (
            temporal_weight_map.n_pool_events
            if temporal_weight_map is not None
            else None
        ),
        "filter_stale_versions": config.filter_stale_versions,
        "source_distribution_map": config.source_distribution_map,
        "n_events_read": n_read,
        "n_stale_filtered": n_stale,
        "n_events_input": n_input,
        "n_groups": n_groups,
        "n_survivorship_discarded": n_survivorship_discarded,
        "n_events_output": n_output,
        "n_summary_expanded": n_summary,
        "n_temporally_distributed": n_temporally_distributed,
        "temporal_weight_key_counts": temporal_weight_key_counts,
        "n_temporal_uniform_fallback": temporal_weight_key_counts.get(
            "uniform_fallback", 0,
        ),
        "n_spatially_distributed": n_spatially_distributed,
        "n_spatial_cells_created": n_spatial_cells_created,
        "n_excluded_where_prec": n_excluded_where_prec,
        "n_passthrough_where_prec": n_passthrough_where_prec,
        "n_filtered": n_filtered,
        "output_path": str(config.output_path),
        "output_digest": output_digest,
        "ledger_version": LEDGER_VERSION,
        "digest_algorithm": DIGEST_SCHEME,
    })

    logger.info(
        "Viewpoint %s built: %d → %d rows (digest: %s)",
        config.version, n_input, n_output, output_digest,
    )

    return ViewpointResult(
        output_path=config.output_path,
        n_events_input=n_input,
        n_events_output=n_output,
        n_summary_expanded=n_summary,
        n_spatially_distributed=n_spatially_distributed,
        n_filtered=n_filtered,
        output_digest=output_digest,
        version=config.version,
    )


# Auto-register
register_builder("ucdp_v1", build_ucdp_v1)
