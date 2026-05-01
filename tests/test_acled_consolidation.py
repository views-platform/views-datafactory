"""Tests for ACLED consolidation — mock-based, no network.

Uses synthetic Parquet snapshots mimicking ACLED harvester output.
"""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from datafactory_consolidation.consolidation_result import (
    ConsolidationResult,
)
from datafactory_consolidation.consolidators.acled import (
    AcledConsolidationConfig,
    _extract_version,
    consolidate_acled,
)
from datafactory_consolidation.event_store import read_store


# ---- Helpers ----


def _make_acled_events(
    n: int = 5, id_start: int = 1,
) -> list[dict]:
    """Create synthetic ACLED-like events."""
    return [
        {
            "event_id_cnty": f"SOM{id_start + i:04d}",
            "event_date": f"2020-{(i % 12) + 1:02d}-15",
            "event_type": "Battles",
            "sub_event_type": "Armed clash",
            "actor1": f"Group A{i}",
            "actor2": f"Group B{i}",
            "country": "Somalia",
            "admin1": "Banadir",
            "latitude": 2.0 + i * 0.1,
            "longitude": 45.0 + i * 0.1,
            "fatalities": i * 3,
            "notes": f"Test event {i}",
            "source": "Test",
            "source_scale": "National",
        }
        for i in range(n)
    ]


def _write_parquet(path: Path, events: list[dict]) -> Path:
    """Write events to Parquet."""
    all_fields = sorted({k for ev in events for k in ev})
    columns = {
        f: [ev.get(f) for ev in events] for f in all_fields
    }
    pa_columns = {
        n: pa.array(v, from_pandas=True)
        for n, v in columns.items()
    }
    table = pa.table(pa_columns)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)
    return path


def _setup_snapshot(
    tmp_path: Path,
    events: list[dict],
    start: int = 2020,
    end: int = 2020,
) -> Path:
    """Write an ACLED snapshot with harvester naming convention."""
    source_dir = tmp_path / "raw"
    _write_parquet(
        source_dir / f"acled_{start}_{end}.parquet", events,
    )
    return source_dir


# ---- Version Extraction ----


class TestVersionExtractionGreen:

    def test_standard_filename(self) -> None:
        p = Path("acled_1997_2025.parquet")
        assert _extract_version(p) == "1997_2025"

    def test_single_year(self) -> None:
        p = Path("acled_2020_2020.parquet")
        assert _extract_version(p) == "2020_2020"


class TestVersionExtractionBeige:

    def test_bad_filename_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot extract"):
            _extract_version(Path("random_file.parquet"))


# ---- Full Consolidation Flow ----


class TestConsolidateAcledGreen:

    def test_first_consolidation(self, tmp_path: Path) -> None:
        """First run creates store with all events."""
        events = _make_acled_events(10)
        source_dir = _setup_snapshot(tmp_path, events)

        config = AcledConsolidationConfig(
            source_dir=source_dir,
            harvest_ledger_path=(
                tmp_path / "prov" / "harvest.jsonl"
            ),
            output_path=(
                tmp_path / "store" / "acled_store.parquet"
            ),
            ledger_path=(
                tmp_path / "prov" / "consolidation.jsonl"
            ),
        )

        result = consolidate_acled(config)

        assert isinstance(result, ConsolidationResult)
        assert result.n_sources == 1
        assert result.n_records_total == 10
        assert result.n_records_new == 10
        assert result.output_path.exists()

        store = read_store(result.output_path)
        assert store is not None
        assert "_source_type" in store.column_names
        assert "_harvest_digest" in store.column_names
        assert all(
            v == "acled"
            for v in store.column("_source_type").to_pylist()
        )

    def test_idempotent_rerun(self, tmp_path: Path) -> None:
        """Re-running with same data adds no new records."""
        events = _make_acled_events(5)
        source_dir = _setup_snapshot(tmp_path, events)

        config = AcledConsolidationConfig(
            source_dir=source_dir,
            harvest_ledger_path=(
                tmp_path / "prov" / "harvest.jsonl"
            ),
            output_path=(
                tmp_path / "store" / "acled_store.parquet"
            ),
            ledger_path=(
                tmp_path / "prov" / "consolidation.jsonl"
            ),
        )

        r1 = consolidate_acled(config)
        r2 = consolidate_acled(config)

        assert r2.n_records_new == 0
        assert r2.n_records_total == r1.n_records_total

    def test_provenance_recorded(self, tmp_path: Path) -> None:
        """Consolidation writes a ledger entry."""
        events = _make_acled_events(3)
        source_dir = _setup_snapshot(tmp_path, events)

        config = AcledConsolidationConfig(
            source_dir=source_dir,
            harvest_ledger_path=(
                tmp_path / "prov" / "harvest.jsonl"
            ),
            output_path=(
                tmp_path / "store" / "acled_store.parquet"
            ),
            ledger_path=(
                tmp_path / "prov" / "consolidation.jsonl"
            ),
        )

        consolidate_acled(config)

        assert config.ledger_path.exists()
        entry = json.loads(
            config.ledger_path.read_text()
            .strip()
            .splitlines()[-1]
        )
        assert entry["dataset"] == "acled_consolidation"
        assert entry["n_records_total"] == 3
        assert "output_digest" in entry
        assert "schema_columns" in entry


class TestConsolidateAcledBeige:

    def test_no_source_files_raises(self, tmp_path: Path) -> None:
        """Empty source dir raises FileNotFoundError."""
        config = AcledConsolidationConfig(
            source_dir=tmp_path / "empty",
            output_path=tmp_path / "store" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )
        with pytest.raises(
            FileNotFoundError, match="No ACLED Parquet"
        ):
            consolidate_acled(config)

    def test_missing_required_field_raises(
        self, tmp_path: Path,
    ) -> None:
        """Events without event_id_cnty raise ValueError."""
        bad_events = [{"country": "Somalia", "fatalities": 5}]
        source_dir = tmp_path / "raw"
        _write_parquet(
            source_dir / "acled_2020_2020.parquet", bad_events,
        )

        config = AcledConsolidationConfig(
            source_dir=source_dir,
            output_path=tmp_path / "store" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )
        with pytest.raises(ValueError, match="missing required"):
            consolidate_acled(config)


# ---- Registration ----


class TestAcledConsolidatorRegistration:

    def test_registered(self) -> None:
        import datafactory_consolidation.consolidators.acled  # noqa: F401
        from datafactory_consolidation.consolidators import (
            list_consolidators,
        )

        assert "acled" in list_consolidators()
