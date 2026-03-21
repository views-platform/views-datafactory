"""Tests for datafactory_consolidation — UCDP event store consolidation.

Uses synthetic Parquet snapshots that mimic harvester output naming
conventions. No network access needed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from datafactory_consolidation.consolidation_result import ConsolidationResult
from datafactory_consolidation.consolidators.ucdp import (
    UcdpConsolidationConfig,
    _extract_annual_version,
    _extract_candidate_version,
    consolidate_ucdp,
)
from datafactory_consolidation.event_store import read_store, write_store

# ---- Helpers ----


def _make_events(n: int = 5, id_start: int = 1) -> list[dict]:
    """Create synthetic UCDP-like events."""
    return [
        {
            "id": id_start + i,
            "country_id": 200 + (i % 3),
            "country": ["Sudan", "DRC", "Somalia"][i % 3],
            "latitude": 4.0 + i * 0.1,
            "longitude": 31.5 + i * 0.1,
            "date_start": f"2023-{(i % 12) + 1:02d}-15",
            "best": i * 5,
            "high": i * 7,
            "low": i * 3,
            "type_of_violence": 1,
            "date_prec": 1,
            "where_prec": 1,
        }
        for i in range(n)
    ]


def _write_parquet(path: Path, events: list[dict]) -> Path:
    """Write events to a Parquet file using the same method as the harvester."""
    all_fields = sorted({k for ev in events for k in ev})
    columns = {f: [ev.get(f) for ev in events] for f in all_fields}
    pa_columns = {n: pa.array(v, from_pandas=True) for n, v in columns.items()}
    table = pa.table(pa_columns)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)
    return path


def _setup_annual(tmp_path: Path, events: list[dict]) -> Path:
    """Write an annual snapshot with the harvester naming convention."""
    annual_dir = tmp_path / "annual"
    _write_parquet(annual_dir / "ucdp_ged_v25.1_1989_2024.parquet", events)
    return annual_dir


def _setup_candidate(
    tmp_path: Path, events: list[dict], version: str = "25.0.1"
) -> Path:
    """Write a candidate snapshot with the harvester naming convention."""
    candidate_dir = tmp_path / "candidate"
    _write_parquet(
        candidate_dir / f"ucdp_ged_candidate_{version}.parquet", events
    )
    return candidate_dir


def _config(
    tmp_path: Path,
    annual_dir: Path | None = None,
    candidate_dir: Path | None = None,
) -> UcdpConsolidationConfig:
    """Build a test config pointing to tmp_path locations."""
    return UcdpConsolidationConfig(
        annual_dir=annual_dir or tmp_path / "annual",
        candidate_dir=candidate_dir or tmp_path / "candidate",
        annual_ledger_path=tmp_path / "prov_annual" / "ledger.jsonl",
        candidate_ledger_path=tmp_path / "prov_cand" / "ledger.jsonl",
        output_path=tmp_path / "consolidated" / "store.parquet",
        ledger_path=tmp_path / "provenance" / "ledger.jsonl",
    )


# ---- Version Extraction ----


class TestVersionExtractionGreen:

    def test_annual_version(self) -> None:
        p = Path("data/ucdp_annual/ucdp_ged_v25.1_1989_2024.parquet")
        assert _extract_annual_version(p) == "25.1"

    def test_candidate_version(self) -> None:
        p = Path("data/ucdp_candidate/ucdp_ged_candidate_25.0.3.parquet")
        assert _extract_candidate_version(p) == "25.0.3"

    def test_candidate_version_double_digit(self) -> None:
        p = Path("ucdp_ged_candidate_25.0.12.parquet")
        assert _extract_candidate_version(p) == "25.0.12"


class TestVersionExtractionRed:

    def test_annual_malformed_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot extract version"):
            _extract_annual_version(Path("random_file.parquet"))

    def test_candidate_malformed_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot extract version"):
            _extract_candidate_version(Path("random_file.parquet"))


# ---- Store I/O ----


class TestStoreIoGreen:

    def test_read_nonexistent_returns_none(self, tmp_path: Path) -> None:
        assert read_store(tmp_path / "nope.parquet") is None

    def test_write_and_read_roundtrip(self, tmp_path: Path) -> None:
        table = pa.table({"id": [1, 2, 3], "value": [10, 20, 30]})
        path = tmp_path / "store.parquet"
        digest = write_store(table, path)

        loaded = read_store(path)
        assert loaded is not None
        assert loaded.num_rows == 3
        assert len(digest) == 16

    def test_write_creates_parent_dirs(self, tmp_path: Path) -> None:
        table = pa.table({"id": [1]})
        path = tmp_path / "deep" / "nested" / "store.parquet"
        write_store(table, path)
        assert path.exists()


# ---- Config ----


class TestUcdpConsolidationConfigGreen:

    def test_defaults(self) -> None:
        cfg = UcdpConsolidationConfig()
        assert cfg.annual_dir == Path("data/ucdp_annual")
        assert cfg.candidate_dir == Path("data/ucdp_candidate")

    def test_frozen(self) -> None:
        cfg = UcdpConsolidationConfig()
        with pytest.raises(AttributeError):
            cfg.annual_dir = Path("other")  # type: ignore[misc]


# ---- Consolidation: Green ----


class TestConsolidateUcdpGreen:

    def test_consolidates_single_annual(self, tmp_path: Path) -> None:
        events = _make_events(5)
        annual_dir = _setup_annual(tmp_path, events)
        cfg = _config(tmp_path, annual_dir=annual_dir)

        result = consolidate_ucdp(cfg)

        assert isinstance(result, ConsolidationResult)
        assert result.n_records_total == 5
        assert result.n_records_new == 5
        assert result.n_sources == 1
        assert result.output_path.exists()

    def test_consolidates_annual_plus_candidate(self, tmp_path: Path) -> None:
        annual_events = _make_events(5, id_start=1)
        candidate_events = _make_events(3, id_start=100)

        annual_dir = _setup_annual(tmp_path, annual_events)
        candidate_dir = _setup_candidate(tmp_path, candidate_events)
        cfg = _config(tmp_path, annual_dir=annual_dir, candidate_dir=candidate_dir)

        result = consolidate_ucdp(cfg)

        assert result.n_records_total == 8
        assert result.n_sources == 2

    def test_preserves_all_source_fields(self, tmp_path: Path) -> None:
        events = _make_events(3)
        annual_dir = _setup_annual(tmp_path, events)
        cfg = _config(tmp_path, annual_dir=annual_dir)

        consolidate_ucdp(cfg)
        table = pq.read_table(cfg.output_path)

        # All original fields must be present
        for field in ("id", "latitude", "longitude", "date_start", "best",
                      "high", "low", "country", "type_of_violence",
                      "date_prec", "where_prec"):
            assert field in table.column_names, f"Missing field: {field}"

    def test_metadata_columns_present(self, tmp_path: Path) -> None:
        events = _make_events(3)
        annual_dir = _setup_annual(tmp_path, events)
        cfg = _config(tmp_path, annual_dir=annual_dir)

        consolidate_ucdp(cfg)
        table = pq.read_table(cfg.output_path)

        assert "_source_type" in table.column_names
        assert "_source_version" in table.column_names
        assert "_ingested_at" in table.column_names

        # Check values
        types = table.column("_source_type").to_pylist()
        assert all(t == "annual" for t in types)

        versions = table.column("_source_version").to_pylist()
        assert all(v == "25.1" for v in versions)

    def test_provenance_recorded(self, tmp_path: Path) -> None:
        events = _make_events(3)
        annual_dir = _setup_annual(tmp_path, events)
        cfg = _config(tmp_path, annual_dir=annual_dir)

        consolidate_ucdp(cfg)

        assert cfg.ledger_path.exists()
        entry = json.loads(
            cfg.ledger_path.read_text().strip().splitlines()[-1]
        )
        assert entry["dataset"] == "ucdp_consolidation"
        assert entry["n_records_total"] == 3
        assert "output_digest" in entry
        assert "source_manifest" in entry

    def test_idempotent(self, tmp_path: Path) -> None:
        """Running twice with same inputs produces same record count."""
        events = _make_events(5)
        annual_dir = _setup_annual(tmp_path, events)
        cfg = _config(tmp_path, annual_dir=annual_dir)

        r1 = consolidate_ucdp(cfg)
        r2 = consolidate_ucdp(cfg)

        assert r1.n_records_total == r2.n_records_total
        assert r2.n_records_new == 0  # No new records on second run

    def test_same_event_both_sources(self, tmp_path: Path) -> None:
        """Same event ID in annual and candidate — both versions preserved."""
        shared_id = 42
        annual_events = [
            {"id": shared_id, "latitude": 4.0, "longitude": 31.5,
             "date_start": "2023-01-15", "best": 10, "high": 12,
             "low": 8, "country_id": 200, "country": "Sudan",
             "type_of_violence": 1, "date_prec": 1, "where_prec": 1},
        ]
        candidate_events = [
            {"id": shared_id, "latitude": 4.0, "longitude": 31.5,
             "date_start": "2023-01-15", "best": 15, "high": 18,
             "low": 12, "country_id": 200, "country": "Sudan",
             "type_of_violence": 1, "date_prec": 1, "where_prec": 1},
        ]

        annual_dir = _setup_annual(tmp_path, annual_events)
        candidate_dir = _setup_candidate(tmp_path, candidate_events)
        cfg = _config(
            tmp_path, annual_dir=annual_dir, candidate_dir=candidate_dir
        )

        result = consolidate_ucdp(cfg)

        # Both versions preserved (not deduplicated by event ID alone)
        assert result.n_records_total == 2

        table = pq.read_table(cfg.output_path)
        ids = table.column("id").to_pylist()
        assert ids.count(shared_id) == 2

        types = set(table.column("_source_type").to_pylist())
        assert types == {"annual", "candidate"}

        # Different best values preserved
        bests = sorted(table.column("best").to_pylist())
        assert bests == [10, 15]

    def test_incremental_adds_new_version(self, tmp_path: Path) -> None:
        """Consolidate, add a new candidate file, consolidate again."""
        annual_events = _make_events(5, id_start=1)
        annual_dir = _setup_annual(tmp_path, annual_events)
        candidate_dir = tmp_path / "candidate"
        cfg = _config(
            tmp_path, annual_dir=annual_dir, candidate_dir=candidate_dir
        )

        # First run: annual only
        r1 = consolidate_ucdp(cfg)
        assert r1.n_records_total == 5

        # Add a candidate file
        candidate_events = _make_events(3, id_start=100)
        _setup_candidate(tmp_path, candidate_events, version="25.0.1")

        # Second run: annual + candidate
        r2 = consolidate_ucdp(cfg)
        assert r2.n_records_total == 8
        assert r2.n_records_new == 3  # Only candidate records are new

        # Verify both source types present
        table = pq.read_table(cfg.output_path)
        types = set(table.column("_source_type").to_pylist())
        assert types == {"annual", "candidate"}

    def test_result_structure(self, tmp_path: Path) -> None:
        events = _make_events(3)
        annual_dir = _setup_annual(tmp_path, events)
        cfg = _config(tmp_path, annual_dir=annual_dir)

        result = consolidate_ucdp(cfg)

        assert isinstance(result.output_path, Path)
        assert isinstance(result.n_sources, int)
        assert isinstance(result.n_records_total, int)
        assert isinstance(result.n_records_new, int)
        assert isinstance(result.output_digest, str)
        assert len(result.output_digest) == 16


# ---- Consolidation: Beige ----


class TestConsolidateUcdpBeige:

    def test_empty_directories_raises(self, tmp_path: Path) -> None:
        cfg = _config(tmp_path)
        with pytest.raises(FileNotFoundError, match="No source"):
            consolidate_ucdp(cfg)

    def test_annual_only(self, tmp_path: Path) -> None:
        """Candidate dir empty/missing — annual alone works."""
        events = _make_events(3)
        annual_dir = _setup_annual(tmp_path, events)
        cfg = _config(tmp_path, annual_dir=annual_dir)

        result = consolidate_ucdp(cfg)
        assert result.n_records_total == 3

        table = pq.read_table(cfg.output_path)
        types = set(table.column("_source_type").to_pylist())
        assert types == {"annual"}

    def test_candidate_only(self, tmp_path: Path) -> None:
        """Annual dir empty/missing — candidate alone works."""
        events = _make_events(3)
        candidate_dir = _setup_candidate(tmp_path, events)
        cfg = _config(tmp_path, candidate_dir=candidate_dir)

        result = consolidate_ucdp(cfg)
        assert result.n_records_total == 3

        table = pq.read_table(cfg.output_path)
        types = set(table.column("_source_type").to_pylist())
        assert types == {"candidate"}


# ---- Consolidation: Red ----


class TestConsolidateUcdpRed:

    def test_malformed_annual_filename_raises(self, tmp_path: Path) -> None:
        annual_dir = tmp_path / "annual"
        _write_parquet(annual_dir / "bad_name.parquet", _make_events(1))
        cfg = _config(tmp_path, annual_dir=annual_dir)

        with pytest.raises(ValueError, match="Cannot extract version"):
            consolidate_ucdp(cfg)

    def test_malformed_candidate_filename_raises(self, tmp_path: Path) -> None:
        candidate_dir = tmp_path / "candidate"
        _write_parquet(candidate_dir / "bad_name.parquet", _make_events(1))
        cfg = _config(tmp_path, candidate_dir=candidate_dir)

        with pytest.raises(ValueError, match="Cannot extract version"):
            consolidate_ucdp(cfg)


# ---- Registry ----


class TestConsolidatorRegistration:

    def test_registered_in_consolidators(self) -> None:
        import datafactory_consolidation.consolidators.ucdp  # noqa: F401
        from datafactory_consolidation.consolidators import list_consolidators

        assert "ucdp" in list_consolidators()


# ---- Vintage Awareness (ADR-017) ----


class TestVintageAwarenessGreen:

    def test_harvest_digest_column_present(
        self, tmp_path: Path
    ) -> None:
        events = _make_events(3)
        annual_dir = _setup_annual(tmp_path, events)
        cfg = _config(tmp_path, annual_dir=annual_dir)

        consolidate_ucdp(cfg)
        table = pq.read_table(cfg.output_path)

        assert "_harvest_digest" in table.column_names
        digests = table.column("_harvest_digest").to_pylist()
        assert all(isinstance(d, str) and len(d) == 16 for d in digests)

    def test_harvest_timestamp_column_present(
        self, tmp_path: Path
    ) -> None:
        events = _make_events(3)
        annual_dir = _setup_annual(tmp_path, events)
        cfg = _config(tmp_path, annual_dir=annual_dir)

        consolidate_ucdp(cfg)
        table = pq.read_table(cfg.output_path)

        assert "_harvest_timestamp" in table.column_names
        timestamps = table.column("_harvest_timestamp").to_pylist()
        assert all(isinstance(t, str) and len(t) > 10 for t in timestamps)

    def test_same_digest_deduplicates(
        self, tmp_path: Path
    ) -> None:
        """Re-consolidating identical data skips (same digest)."""
        events = _make_events(5)
        annual_dir = _setup_annual(tmp_path, events)
        cfg = _config(tmp_path, annual_dir=annual_dir)

        r1 = consolidate_ucdp(cfg)
        r2 = consolidate_ucdp(cfg)

        assert r1.n_records_total == r2.n_records_total
        assert r2.n_records_new == 0

    def test_different_digest_preserves_both(
        self, tmp_path: Path
    ) -> None:
        """Modified source with different digest → both vintages kept."""
        events_v1 = _make_events(3, id_start=1)
        annual_dir = _setup_annual(tmp_path, events_v1)
        cfg = _config(tmp_path, annual_dir=annual_dir)

        r1 = consolidate_ucdp(cfg)
        assert r1.n_records_total == 3

        # Modify the source file (same filename, different content)
        events_v2 = _make_events(3, id_start=1)
        events_v2[0]["best"] = 999  # Change a value
        _write_parquet(
            annual_dir / "ucdp_ged_v25.1_1989_2024.parquet",
            events_v2,
        )

        r2 = consolidate_ucdp(cfg)

        # Both vintages preserved: 3 original + 3 updated = 6
        assert r2.n_records_total == 6
        assert r2.n_records_new == 3

    def test_fallback_without_ledger(
        self, tmp_path: Path
    ) -> None:
        """Works without harvest ledger — uses file digest."""
        events = _make_events(3)
        annual_dir = _setup_annual(tmp_path, events)
        cfg = _config(tmp_path, annual_dir=annual_dir)
        # Ledger paths don't exist — should fall back gracefully

        result = consolidate_ucdp(cfg)

        assert result.n_records_total == 3
        table = pq.read_table(cfg.output_path)
        assert "_harvest_digest" in table.column_names
