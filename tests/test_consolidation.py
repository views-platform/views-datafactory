"""Tests for datafactory_consolidation — UCDP event store consolidation.

Uses synthetic Parquet snapshots that mimic harvester output naming
conventions. No network access needed.
"""

from __future__ import annotations

import json
import threading
import unittest.mock
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from datafactory_consolidation.consolidation_result import ConsolidationResult
from datafactory_consolidation.consolidators.ucdp import (
    UcdpConsolidationConfig,
    _extract_annual_version,
    _extract_candidate_version,
    _extract_dot9_version,
    consolidate_ucdp,
)
from datafactory_consolidation.event_store import read_store, write_store
from datafactory_provenance import compute_file_digest

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


def _setup_dot9(
    tmp_path: Path,
    events: list[dict],
    version: str = "25.9.11",
) -> Path:
    """Write a .9 snapshot with the harvester naming convention."""
    dot9_dir = tmp_path / "dot9"
    _write_parquet(
        dot9_dir / f"ucdp_ged_dot9_{version}.parquet", events
    )
    return dot9_dir


def _config(
    tmp_path: Path,
    annual_dir: Path | None = None,
    candidate_dir: Path | None = None,
    dot9_dir: Path | None = None,
) -> UcdpConsolidationConfig:
    """Build a test config pointing to tmp_path locations."""
    return UcdpConsolidationConfig(
        annual_dir=annual_dir or tmp_path / "annual",
        candidate_dir=candidate_dir or tmp_path / "candidate",
        dot9_dir=dot9_dir or tmp_path / "dot9",
        annual_ledger_path=tmp_path / "prov_annual" / "ledger.jsonl",
        candidate_ledger_path=tmp_path / "prov_cand" / "ledger.jsonl",
        dot9_ledger_path=tmp_path / "prov_dot9" / "ledger.jsonl",
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

    def test_dot9_version(self) -> None:
        p = Path("ucdp_ged_dot9_25.9.11.parquet")
        assert _extract_dot9_version(p) == "25.9.11"

    def test_dot9_version_single_digit(self) -> None:
        p = Path("ucdp_ged_dot9_18.9.1.parquet")
        assert _extract_dot9_version(p) == "18.9.1"


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
        assert cfg.annual_dir == Path("data/raw/ucdp_annual")
        assert cfg.candidate_dir == Path("data/raw/ucdp_candidate")

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

        assert result.output_path.exists()
        assert result.n_sources == 1
        assert result.n_records_total == 3
        assert result.n_records_new == 3
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

    def test_dot9_only(self, tmp_path: Path) -> None:
        """.9 dir only — works alone."""
        events = _make_events(3)
        dot9_dir = _setup_dot9(tmp_path, events)
        cfg = _config(tmp_path, dot9_dir=dot9_dir)

        result = consolidate_ucdp(cfg)
        assert result.n_records_total == 3

        table = pq.read_table(cfg.output_path)
        types = set(table.column("_source_type").to_pylist())
        assert types == {"dot9"}

    def test_all_three_sources(self, tmp_path: Path) -> None:
        """Annual + candidate + .9 → all three source types."""
        annual_events = _make_events(3, id_start=1)
        candidate_events = _make_events(2, id_start=100)
        dot9_events = _make_events(4, id_start=200)

        annual_dir = _setup_annual(tmp_path, annual_events)
        candidate_dir = _setup_candidate(tmp_path, candidate_events)
        dot9_dir = _setup_dot9(tmp_path, dot9_events)
        cfg = _config(
            tmp_path,
            annual_dir=annual_dir,
            candidate_dir=candidate_dir,
            dot9_dir=dot9_dir,
        )

        result = consolidate_ucdp(cfg)
        assert result.n_records_total == 9
        assert result.n_sources == 3

        table = pq.read_table(cfg.output_path)
        types = set(table.column("_source_type").to_pylist())
        assert types == {"annual", "candidate", "dot9"}

    def test_dot9_metadata_correct(self, tmp_path: Path) -> None:
        """.9 events tagged with correct source_type and version."""
        events = _make_events(2)
        dot9_dir = _setup_dot9(
            tmp_path, events, version="25.9.11"
        )
        cfg = _config(tmp_path, dot9_dir=dot9_dir)

        consolidate_ucdp(cfg)
        table = pq.read_table(cfg.output_path)

        types = table.column("_source_type").to_pylist()
        assert all(t == "dot9" for t in types)

        versions = table.column("_source_version").to_pylist()
        assert all(v == "25.9.11" for v in versions)


# ---- Consolidation: Red ----


class TestConsolidateUcdpRed:

    def test_malformed_annual_filename_skipped(self, tmp_path: Path) -> None:
        """Non-matching filenames in source dirs are silently skipped."""
        annual_dir = tmp_path / "annual"
        _write_parquet(annual_dir / "bad_name.parquet", _make_events(1))
        cfg = _config(tmp_path, annual_dir=annual_dir)

        with pytest.raises(FileNotFoundError, match="No source Parquet"):
            consolidate_ucdp(cfg)

    def test_malformed_candidate_filename_skipped(self, tmp_path: Path) -> None:
        """Non-matching filenames in source dirs are silently skipped."""
        candidate_dir = tmp_path / "candidate"
        _write_parquet(candidate_dir / "bad_name.parquet", _make_events(1))
        cfg = _config(tmp_path, candidate_dir=candidate_dir)

        with pytest.raises(FileNotFoundError, match="No source Parquet"):
            consolidate_ucdp(cfg)

    def test_frozen_config_mutation(self) -> None:
        """UcdpConsolidationConfig rejects mutation."""
        cfg = UcdpConsolidationConfig()
        with pytest.raises(AttributeError):
            cfg.annual_dir = Path("other")  # type: ignore[misc]


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


class TestRowCountInvariants:
    """C-146: consolidation must assert row-count arithmetic."""

    def test_result_includes_n_records_before(
        self, tmp_path: Path
    ) -> None:
        """ConsolidationResult exposes n_records_before."""
        events = _make_events(5)
        annual_dir = _setup_annual(tmp_path, events)
        cfg = _config(tmp_path, annual_dir=annual_dir)

        result = consolidate_ucdp(cfg)

        assert hasattr(result, "n_records_before")
        assert result.n_records_before == 0

    def test_merge_arithmetic(self, tmp_path: Path) -> None:
        """n_records_total == n_records_before + n_records_new."""
        annual_events = _make_events(5, id_start=1)
        candidate_events = _make_events(3, id_start=100)

        annual_dir = _setup_annual(tmp_path, annual_events)
        cfg = _config(tmp_path, annual_dir=annual_dir)
        r1 = consolidate_ucdp(cfg)

        candidate_dir = _setup_candidate(tmp_path, candidate_events)
        cfg2 = _config(
            tmp_path,
            annual_dir=annual_dir,
            candidate_dir=candidate_dir,
        )
        r2 = consolidate_ucdp(cfg2)

        assert r2.n_records_before == r1.n_records_total
        assert r2.n_records_total == r2.n_records_before + r2.n_records_new

    def test_concat_preserves_all_source_rows(
        self, tmp_path: Path
    ) -> None:
        """Total rows == sum of individual source file rows."""
        annual_events = _make_events(5, id_start=1)
        candidate_events = _make_events(3, id_start=100)
        dot9_events = _make_events(4, id_start=200)

        annual_dir = _setup_annual(tmp_path, annual_events)
        candidate_dir = _setup_candidate(tmp_path, candidate_events)
        dot9_dir = _setup_dot9(tmp_path, dot9_events)
        cfg = _config(
            tmp_path,
            annual_dir=annual_dir,
            candidate_dir=candidate_dir,
            dot9_dir=dot9_dir,
        )

        result = consolidate_ucdp(cfg)

        assert result.n_records_total == 5 + 3 + 4

    def test_concat_mismatch_raises(
        self, tmp_path: Path
    ) -> None:
        """Row-count mismatch after concat raises RuntimeError."""
        events = _make_events(5)
        annual_dir = _setup_annual(tmp_path, events)
        cfg = _config(tmp_path, annual_dir=annual_dir)

        original_concat = pa.concat_tables

        def drop_one_row(*args, **kwargs):
            result = original_concat(*args, **kwargs)
            return result.slice(0, result.num_rows - 1)

        with (
            pytest.raises(RuntimeError, match="[Rr]ow count"),
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setattr(pa, "concat_tables", drop_one_row)
            consolidate_ucdp(cfg)


# ---------------------------------------------------------------------------
# Characterization: event_store crash-safety (C-267, #195)
# ---------------------------------------------------------------------------


def _sample_table(n: int = 5) -> pa.Table:
    return pa.table({"id": list(range(n)), "value": [f"v{i}" for i in range(n)]})


class TestStoreCharacterization:
    """Pin event_store read/write behavior to catch crash-safety regressions."""

    def test_write_produces_complete_file(self, tmp_path: Path) -> None:
        store = tmp_path / "store.parquet"
        original = _sample_table()
        write_store(original, store)
        roundtrip = read_store(store)
        assert roundtrip is not None
        assert roundtrip.equals(original)

    def test_write_uses_temp_file(self, tmp_path: Path) -> None:
        store = tmp_path / "store.parquet"
        table = _sample_table()
        import tempfile as _tempfile

        with unittest.mock.patch(
            "tempfile.mkstemp", wraps=_tempfile.mkstemp,
        ) as mock_mkstemp:
            write_store(table, store)
        mock_mkstemp.assert_called_once()

    def test_read_returns_none_on_missing_path(self, tmp_path: Path) -> None:
        result = read_store(tmp_path / "nonexistent.parquet")
        assert result is None

    def test_write_returns_content_digest(self, tmp_path: Path) -> None:
        store = tmp_path / "store.parquet"
        table = _sample_table()
        digest = write_store(table, store)
        assert isinstance(digest, str)
        assert len(digest) == 16
        assert all(c in "0123456789abcdef" for c in digest)
        assert digest == compute_file_digest(store)

    def test_concurrent_reads_safe(self, tmp_path: Path) -> None:
        store = tmp_path / "store.parquet"
        original = _sample_table(100)
        write_store(original, store)

        results: list[pa.Table | None] = [None, None]
        errors: list[Exception | None] = [None, None]

        def reader(idx: int) -> None:
            try:
                results[idx] = read_store(store)
            except Exception as exc:
                errors[idx] = exc

        t1 = threading.Thread(target=reader, args=(0,))
        t2 = threading.Thread(target=reader, args=(1,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert errors[0] is None, f"thread 0 error: {errors[0]}"
        assert errors[1] is None, f"thread 1 error: {errors[1]}"
        assert results[0] is not None and results[0].equals(original)
        assert results[1] is not None and results[1].equals(original)

    def test_write_overwrites_existing(self, tmp_path: Path) -> None:
        store = tmp_path / "store.parquet"
        old = _sample_table(3)
        new = _sample_table(7)
        write_store(old, store)
        write_store(new, store)
        result = read_store(store)
        assert result is not None
        assert result.num_rows == 7
        assert result.equals(new)


# ---- Provenance locking hardening (C-294, C-295, #238) ----


class TestDigestUnderLockRed:
    """Digest must be computed inside the file lock (ADR-005)."""

    def test_digest_matches_file_contents(
        self, tmp_path: Path,
    ) -> None:
        """write_store returns digest matching on-disk file."""
        store = tmp_path / "store.parquet"
        table = _sample_table(5)
        digest = write_store(table, store)
        assert digest == compute_file_digest(store)

    def test_digest_changes_on_rewrite(
        self, tmp_path: Path,
    ) -> None:
        """Rewriting with different data produces different digest."""
        store = tmp_path / "store.parquet"
        d1 = write_store(_sample_table(3), store)
        d2 = write_store(_sample_table(7), store)
        assert d1 != d2


class TestFileLockTimeoutRed:
    """file_lock timeout behavior (C-295, ADR-005)."""

    def test_lock_timeout_raises(self, tmp_path: Path) -> None:
        """Held lock + short timeout → TimeoutError."""
        from datafactory_provenance.digests_and_ledgers import (
            file_lock,
        )

        target = tmp_path / "data.parquet"
        target.touch()

        lock_path = target.with_suffix(".parquet.lock")
        import fcntl

        lock_file = open(lock_path, "w")  # noqa: SIM115
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            with pytest.raises(TimeoutError, match="Timed out"), \
                 file_lock(target, timeout=0.3):
                pass  # pragma: no cover
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
            lock_file.close()

    def test_lock_acquires_after_release(
        self, tmp_path: Path,
    ) -> None:
        """Lock acquired once holder releases."""
        from datafactory_provenance.digests_and_ledgers import (
            file_lock,
        )

        target = tmp_path / "data.parquet"
        target.touch()

        acquired = threading.Event()
        released = threading.Event()

        def hold_then_release() -> None:
            with file_lock(target, timeout=5.0):
                acquired.set()
                released.wait(timeout=2.0)

        t = threading.Thread(target=hold_then_release)
        t.start()
        acquired.wait(timeout=2.0)

        released.set()

        with file_lock(target, timeout=5.0):
            pass

        t.join(timeout=5.0)

    def test_lock_timeout_error_message_includes_path(
        self, tmp_path: Path,
    ) -> None:
        """TimeoutError message names the lock file path."""
        import fcntl as _fcntl

        from datafactory_provenance.digests_and_ledgers import (
            file_lock,
        )

        target = tmp_path / "data.parquet"
        target.touch()
        lock_path = target.with_suffix(".parquet.lock")

        lock_file = open(lock_path, "w")  # noqa: SIM115
        _fcntl.flock(lock_file, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
        try:
            with pytest.raises(
                TimeoutError, match=str(lock_path),
            ), file_lock(target, timeout=0.3):
                pass  # pragma: no cover
        finally:
            _fcntl.flock(lock_file, _fcntl.LOCK_UN)
            lock_file.close()
