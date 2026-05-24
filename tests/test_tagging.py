"""Direct tests for datafactory_consolidation.tagging."""

from __future__ import annotations

import pyarrow as pa

from datafactory_consolidation.tagging import tag_table


def test_tag_table_adds_metadata_columns() -> None:
    """tag_table adds 5 metadata columns without removing originals."""
    original = pa.table({"id": [1, 2, 3], "value": [10, 20, 30]})

    tagged = tag_table(
        original,
        source_type="annual",
        source_version="25.1",
        ingested_at="2026-01-01T00:00:00",
        harvest_digest="sha256:abc123",
        harvest_timestamp="2026-01-01T00:00:00",
    )

    assert "id" in tagged.column_names
    assert "value" in tagged.column_names
    assert "_source_type" in tagged.column_names
    assert "_source_version" in tagged.column_names
    assert "_ingested_at" in tagged.column_names
    assert "_harvest_digest" in tagged.column_names
    assert "_harvest_timestamp" in tagged.column_names
    assert tagged.num_rows == 3
    assert tagged.column("_source_type").to_pylist() == [
        "annual", "annual", "annual",
    ]
