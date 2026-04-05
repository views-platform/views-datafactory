"""Schema evolution test: consolidation handles column changes.

Addresses C-61: no test for what happens when Parquet columns are
added or removed between consolidation vintages.

Tests that pa.concat_tables(promote_options="default") correctly
handles the three realistic scenarios:
1. New column added by UCDP (e.g., a new field in a later version)
2. Column removed by UCDP (present in old data, absent in new)
3. Mixed schemas across annual, candidate, and .9 sources
"""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from datafactory_consolidation.consolidators.ucdp import (
    UcdpConsolidationConfig,
    consolidate_ucdp,
)
from datafactory_consolidation.event_store import read_store


def _write_parquet(path: Path, events: list[dict]) -> Path:
    """Write events to Parquet with inferred schema."""
    all_fields = sorted({k for ev in events for k in ev})
    columns = {f: [ev.get(f) for ev in events] for f in all_fields}
    pa_columns = {
        n: pa.array(v, from_pandas=True) for n, v in columns.items()
    }
    table = pa.table(pa_columns)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)
    return path


def _base_event(i: int) -> dict:
    """Minimal event with required fields."""
    return {
        "id": 1000 + i,
        "country_id": 200,
        "latitude": 4.0 + i * 0.1,
        "longitude": 31.5,
        "date_start": f"2023-{(i % 12) + 1:02d}-15",
        "best": i * 3,
        "high": i * 5,
        "low": i,
        "type_of_violence": 1,
        "date_prec": 1,
        "where_prec": 1,
    }


def _config(tmp_path: Path) -> UcdpConsolidationConfig:
    """Config pointing to tmp_path subdirectories."""
    return UcdpConsolidationConfig(
        annual_dir=tmp_path / "annual",
        candidate_dir=tmp_path / "candidate",
        dot9_dir=tmp_path / "dot9",
        annual_ledger_path=tmp_path / "prov_a" / "l.jsonl",
        candidate_ledger_path=tmp_path / "prov_c" / "l.jsonl",
        dot9_ledger_path=tmp_path / "prov_d" / "l.jsonl",
        output_path=tmp_path / "out" / "store.parquet",
        ledger_path=tmp_path / "prov" / "ledger.jsonl",
    )


class TestSchemaEvolutionGreen:
    """Schema evolution: column additions and removals."""

    def test_new_column_added_in_later_version(
        self, tmp_path: Path
    ) -> None:
        """A new column in candidate data should appear as null
        in the annual rows after consolidation.
        """
        # Annual: standard fields
        annual_events = [_base_event(i) for i in range(3)]
        _write_parquet(
            tmp_path / "annual" / "ucdp_ged_v25.1_1989_2024.parquet",
            annual_events,
        )

        # Candidate: adds a new "confidence" field
        cand_events = [
            {**_base_event(i + 100), "confidence": 0.85}
            for i in range(2)
        ]
        _write_parquet(
            tmp_path / "candidate" / "ucdp_ged_candidate_25.0.1.parquet",
            cand_events,
        )

        config = _config(tmp_path)
        result = consolidate_ucdp(config)

        store = read_store(config.output_path)
        assert store is not None
        assert result.n_records_total == 5

        # "confidence" column exists in consolidated store
        assert "confidence" in store.column_names

        # Annual rows have null for the new column
        confidence_vals = store.column("confidence").to_pylist()
        source_types = store.column("_source_type").to_pylist()

        for val, stype in zip(
            confidence_vals, source_types, strict=True
        ):
            if stype == "annual":
                assert val is None, (
                    "Annual rows should have null for new column"
                )
            else:
                assert val == 0.85, (
                    "Candidate rows should preserve new column"
                )

    def test_column_removed_in_later_version(
        self, tmp_path: Path
    ) -> None:
        """If a column disappears from new data, old rows keep it
        and new rows get null.
        """
        # Annual: has "region_code" field
        annual_events = [
            {**_base_event(i), "region_code": 42}
            for i in range(3)
        ]
        _write_parquet(
            tmp_path / "annual" / "ucdp_ged_v25.1_1989_2024.parquet",
            annual_events,
        )

        # Candidate: does NOT have "region_code"
        cand_events = [_base_event(i + 100) for i in range(2)]
        _write_parquet(
            tmp_path / "candidate" / "ucdp_ged_candidate_25.0.1.parquet",
            cand_events,
        )

        config = _config(tmp_path)
        result = consolidate_ucdp(config)

        store = read_store(config.output_path)
        assert store is not None
        assert result.n_records_total == 5

        # "region_code" column preserved from annual data
        assert "region_code" in store.column_names

        region_vals = store.column("region_code").to_pylist()
        source_types = store.column("_source_type").to_pylist()

        for val, stype in zip(
            region_vals, source_types, strict=True
        ):
            if stype == "annual":
                assert val == 42
            else:
                assert val is None, (
                    "Candidate rows should have null for "
                    "removed column"
                )

    def test_mixed_schemas_across_three_streams(
        self, tmp_path: Path
    ) -> None:
        """All three streams with different extra columns consolidate
        without error.
        """
        # Annual: has "region_code"
        annual_events = [
            {**_base_event(i), "region_code": 42}
            for i in range(2)
        ]
        _write_parquet(
            tmp_path / "annual" / "ucdp_ged_v25.1_1989_2024.parquet",
            annual_events,
        )

        # Candidate: has "confidence"
        cand_events = [
            {**_base_event(i + 100), "confidence": 0.9}
            for i in range(2)
        ]
        _write_parquet(
            tmp_path / "candidate" / "ucdp_ged_candidate_25.0.1.parquet",
            cand_events,
        )

        # Dot9: has "quality_flag"
        dot9_events = [
            {**_base_event(i + 200), "quality_flag": "A"}
            for i in range(2)
        ]
        _write_parquet(
            tmp_path / "dot9" / "ucdp_ged_dot9_25.9.1.parquet",
            dot9_events,
        )

        config = _config(tmp_path)
        result = consolidate_ucdp(config)

        store = read_store(config.output_path)
        assert store is not None
        assert result.n_records_total == 6

        # All three extra columns exist
        assert "region_code" in store.column_names
        assert "confidence" in store.column_names
        assert "quality_flag" in store.column_names

    def test_schema_fingerprint_changes_on_new_column(
        self, tmp_path: Path
    ) -> None:
        """Consolidation ledger records schema fingerprint that
        changes when columns are added.
        """
        import json

        # First consolidation: standard fields only
        annual_events = [_base_event(i) for i in range(3)]
        _write_parquet(
            tmp_path / "annual" / "ucdp_ged_v25.1_1989_2024.parquet",
            annual_events,
        )

        config = _config(tmp_path)
        consolidate_ucdp(config)

        ledger_lines = (
            config.ledger_path.read_text().strip().splitlines()
        )
        entry1 = json.loads(ledger_lines[-1])
        fp1 = entry1["schema_fingerprint"]
        cols1 = entry1["schema_columns"]

        # Second consolidation: add candidate with extra column
        cand_events = [
            {**_base_event(i + 100), "new_field": "x"}
            for i in range(2)
        ]
        _write_parquet(
            tmp_path / "candidate" / "ucdp_ged_candidate_25.0.1.parquet",
            cand_events,
        )

        consolidate_ucdp(config)

        ledger_lines = (
            config.ledger_path.read_text().strip().splitlines()
        )
        entry2 = json.loads(ledger_lines[-1])
        fp2 = entry2["schema_fingerprint"]
        cols2 = entry2["schema_columns"]

        assert fp1 != fp2, (
            "Schema fingerprint should change when columns are added"
        )
        assert "new_field" not in cols1
        assert "new_field" in cols2
