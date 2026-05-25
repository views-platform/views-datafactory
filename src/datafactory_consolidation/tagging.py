"""Consolidation metadata tagging for PyArrow tables."""

from __future__ import annotations

import pyarrow as pa


def tag_table(
    table: pa.Table,
    *,
    source_type: str,
    source_version: str,
    ingested_at: str,
    harvest_digest: str,
    harvest_timestamp: str,
) -> pa.Table:
    """Add consolidation metadata columns to a PyArrow table.

    Adds _source_type, _source_version, _ingested_at,
    _harvest_digest, and _harvest_timestamp columns without
    removing any existing columns (lossless per ADR-013).
    Vintage-aware per ADR-017.
    """
    n = table.num_rows
    return (
        table.append_column(
            "_source_type",
            pa.array([source_type] * n, type=pa.string()),
        )
        .append_column(
            "_source_version",
            pa.array([source_version] * n, type=pa.string()),
        )
        .append_column(
            "_ingested_at",
            pa.array([ingested_at] * n, type=pa.string()),
        )
        .append_column(
            "_harvest_digest",
            pa.array([harvest_digest] * n, type=pa.string()),
        )
        .append_column(
            "_harvest_timestamp",
            pa.array([harvest_timestamp] * n, type=pa.string()),
        )
    )
