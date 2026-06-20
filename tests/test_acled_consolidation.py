"""Tests for ACLED consolidation — mock-based, no network.

Uses synthetic Parquet snapshots mimicking ACLED harvester output.
"""

from __future__ import annotations

import json
import logging
import os
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


# ---- Red Team (Adversarial) ----


class TestConsolidateAcledRed:

    def test_malformed_filename_skipped(
        self, tmp_path: Path,
    ) -> None:
        """Non-ACLED filename in source dir is silently skipped."""
        source_dir = tmp_path / "raw"
        _write_parquet(
            source_dir / "bad_name.parquet",
            _make_acled_events(1),
        )

        config = AcledConsolidationConfig(
            source_dir=source_dir,
            output_path=tmp_path / "store" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )
        with pytest.raises(
            FileNotFoundError, match="No ACLED Parquet files"
        ):
            consolidate_acled(config)

    def test_archive_file_coexists_with_snapshot(
        self, tmp_path: Path,
    ) -> None:
        """Archive files alongside valid snapshots are ignored."""
        source_dir = tmp_path / "raw"
        events = _make_acled_events(5)
        _write_parquet(
            source_dir / "acled_2020_2020.parquet", events,
        )
        _write_parquet(
            source_dir / "acled_2020_2020_20260601_193236.parquet",
            events,
        )

        config = AcledConsolidationConfig(
            source_dir=source_dir,
            output_path=tmp_path / "store" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )
        result = consolidate_acled(config)
        assert result.n_records_total == 5

    def test_corrupted_parquet_raises(
        self, tmp_path: Path,
    ) -> None:
        """Binary garbage with valid name raises ArrowInvalid."""
        source_dir = tmp_path / "raw"
        source_dir.mkdir(parents=True)
        (source_dir / "acled_2020_2020.parquet").write_bytes(
            b"not a parquet file"
        )

        config = AcledConsolidationConfig(
            source_dir=source_dir,
            output_path=tmp_path / "store" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )
        with pytest.raises(
            (pa.lib.ArrowInvalid, OSError),
        ):
            consolidate_acled(config)

    def test_schema_drift_columns_promoted(
        self, tmp_path: Path,
    ) -> None:
        """Snapshots with different columns are promoted."""
        source_dir = tmp_path / "raw"

        events_v1 = _make_acled_events(3)
        _write_parquet(
            source_dir / "acled_2020_2020.parquet", events_v1,
        )

        events_v2 = _make_acled_events(3, id_start=100)
        for ev in events_v2:
            ev["new_column"] = "extra_data"
        _write_parquet(
            source_dir / "acled_2021_2021.parquet", events_v2,
        )

        config = AcledConsolidationConfig(
            source_dir=source_dir,
            output_path=tmp_path / "store" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )

        result = consolidate_acled(config)
        assert result.n_records_total == 6

        store = read_store(result.output_path)
        assert "new_column" in store.column_names

    def test_frozen_config_mutation(self) -> None:
        """AcledConsolidationConfig rejects mutation."""
        cfg = AcledConsolidationConfig()
        with pytest.raises(AttributeError):
            cfg.source_dir = Path("other")  # type: ignore[misc]


# ---- Registration ----


class TestAcledConsolidatorRegistration:

    def test_registered(self) -> None:
        import datafactory_consolidation.consolidators.acled  # noqa: F401
        from datafactory_consolidation.consolidators import (
            list_consolidators,
        )

        assert "acled" in list_consolidators()


# ---- Cross-File Dedup (C-251, #138) ----


def _make_config(
    tmp_path: Path, source_dir: Path,
) -> AcledConsolidationConfig:
    """Build consolidation config pointing at tmp directories."""
    return AcledConsolidationConfig(
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


class TestConsolidateAcledCrossFileDedup:
    """Cross-file dedup: same event_id_cnty in different files."""

    def test_overlapping_files_no_double_count(
        self, tmp_path: Path,
    ) -> None:
        """Two files with overlapping events produce no duplicates.

        acled_2020_2025.parquet has 5 events (ids 1-5).
        acled_2025_2025.parquet has 3 of those same events (ids 3-5).
        Result should have exactly 5 unique events.
        """
        source_dir = tmp_path / "raw"
        range_events = _make_acled_events(5, id_start=1)
        _write_parquet(
            source_dir / "acled_2020_2025.parquet",
            range_events,
        )
        overlap_events = _make_acled_events(3, id_start=3)
        _write_parquet(
            source_dir / "acled_2025_2025.parquet",
            overlap_events,
        )

        config = _make_config(tmp_path, source_dir)
        result = consolidate_acled(config)

        assert result.n_records_total == 5

        store = read_store(result.output_path)
        eids = store.column("event_id_cnty").to_pylist()
        assert len(eids) == len(set(eids))

    def test_latest_harvest_wins(
        self, tmp_path: Path,
    ) -> None:
        """Same event in two files with different data — latest wins.

        Old file has fatalities=0, new file has fatalities=99.
        """
        source_dir = tmp_path / "raw"

        old_events = [
            {
                "event_id_cnty": "SOM0001",
                "event_date": "2025-01-15",
                "event_type": "Battles",
                "sub_event_type": "Armed clash",
                "actor1": "Group A",
                "actor2": "Group B",
                "country": "Somalia",
                "admin1": "Banadir",
                "latitude": 2.0,
                "longitude": 45.0,
                "fatalities": 0,
                "notes": "old version",
                "source": "Test",
                "source_scale": "National",
            },
        ]
        new_events = [
            {
                **old_events[0],
                "fatalities": 99,
                "notes": "updated version",
            },
        ]
        old_path = source_dir / "acled_2020_2025.parquet"
        new_path = source_dir / "acled_2025_2025.parquet"
        _write_parquet(old_path, old_events)
        _write_parquet(new_path, new_events)
        # Guarantee distinct mtimes — filesystem resolution can
        # make both files appear same-second, causing tie in dedup.
        os.utime(old_path, (1_000_000, 1_000_000))
        os.utime(new_path, (2_000_000, 2_000_000))

        config = _make_config(tmp_path, source_dir)
        result = consolidate_acled(config)

        assert result.n_records_total == 1
        store = read_store(result.output_path)
        fatalities = store.column("fatalities").to_pylist()
        assert fatalities == [99]

    def test_overlap_detection_warns(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Overlapping year ranges produce a warning."""
        source_dir = tmp_path / "raw"
        _write_parquet(
            source_dir / "acled_2020_2025.parquet",
            _make_acled_events(3, id_start=1),
        )
        _write_parquet(
            source_dir / "acled_2025_2025.parquet",
            _make_acled_events(2, id_start=10),
        )

        config = _make_config(tmp_path, source_dir)
        with caplog.at_level(logging.WARNING):
            consolidate_acled(config)

        overlap_warnings = [
            r for r in caplog.records
            if "overlap" in r.message.lower()
        ]
        assert len(overlap_warnings) >= 1

    def test_full_overlap_subset(
        self, tmp_path: Path,
    ) -> None:
        """Range file + subset file with identical events.

        acled_2020_2025.parquet has events for ids 1-10.
        acled_2025_2025.parquet has same events for ids 8-10.
        Store should contain exactly 10 events.
        """
        source_dir = tmp_path / "raw"
        all_events = _make_acled_events(10, id_start=1)
        _write_parquet(
            source_dir / "acled_2020_2025.parquet",
            all_events,
        )
        subset_events = _make_acled_events(3, id_start=8)
        _write_parquet(
            source_dir / "acled_2025_2025.parquet",
            subset_events,
        )

        config = _make_config(tmp_path, source_dir)
        result = consolidate_acled(config)

        assert result.n_records_total == 10
        store = read_store(result.output_path)
        eids = store.column("event_id_cnty").to_pylist()
        assert len(eids) == len(set(eids))

    def test_disjoint_files_no_dedup(
        self, tmp_path: Path,
    ) -> None:
        """Two files with non-overlapping events preserve all."""
        source_dir = tmp_path / "raw"
        _write_parquet(
            source_dir / "acled_2020_2020.parquet",
            _make_acled_events(5, id_start=1),
        )
        _write_parquet(
            source_dir / "acled_2021_2021.parquet",
            _make_acled_events(5, id_start=100),
        )

        config = _make_config(tmp_path, source_dir)
        result = consolidate_acled(config)

        assert result.n_records_total == 10

    def test_idempotent_with_overlapping_source_files(
        self, tmp_path: Path,
    ) -> None:
        """Consolidate twice with overlapping files — second adds 0."""
        source_dir = tmp_path / "raw"
        _write_parquet(
            source_dir / "acled_2020_2025.parquet",
            _make_acled_events(5, id_start=1),
        )
        _write_parquet(
            source_dir / "acled_2025_2025.parquet",
            _make_acled_events(3, id_start=3),
        )

        config = _make_config(tmp_path, source_dir)
        r1 = consolidate_acled(config)
        r2 = consolidate_acled(config)

        assert r1.n_records_total == 5
        assert r2.n_records_new == 0
        assert r2.n_records_total == 5


# ---- Cross-run dedup: latest-wins (C-252, #210) ----


def _base_event(
    event_id: str = "SOM0001",
    fatalities: int = 0,
) -> dict:
    """Single ACLED event with controllable id and fatalities."""
    return {
        "event_id_cnty": event_id,
        "event_date": "2025-01-15",
        "event_type": "Battles",
        "sub_event_type": "Armed clash",
        "actor1": "Group A",
        "actor2": "Group B",
        "country": "Somalia",
        "admin1": "Banadir",
        "latitude": 2.0,
        "longitude": 45.0,
        "fatalities": fatalities,
        "notes": f"fatalities={fatalities}",
        "source": "Test",
        "source_scale": "National",
    }


class TestCrossRunDedupLatestWins:
    """Cross-run dedup must keep the latest version of revised events.

    ADR-028: ACLED has no vintage semantics — only the most recent
    version of each event matters. This applies to both within-run
    AND cross-run deduplication. C-252 documents the bug where
    cross-run used first-seen-wins instead of latest-wins.
    """

    def test_revised_event_replaces_stale(
        self, tmp_path: Path,
    ) -> None:
        """Re-consolidation with newer timestamp replaces stale event."""
        source_dir = tmp_path / "raw"

        # Run 1: event with fatalities=0
        path1 = _write_parquet(
            source_dir / "acled_2020_2025.parquet",
            [_base_event("SOM0001", fatalities=0)],
        )
        os.utime(path1, (1_000_000, 1_000_000))

        config = _make_config(tmp_path, source_dir)
        consolidate_acled(config)

        store = read_store(config.output_path)
        assert store.column("fatalities").to_pylist() == [0]

        # Run 2: add file with revised event (fatalities=99, later mtime)
        path2 = _write_parquet(
            source_dir / "acled_2025_2025.parquet",
            [_base_event("SOM0001", fatalities=99)],
        )
        os.utime(path2, (2_000_000, 2_000_000))

        consolidate_acled(config)

        store = read_store(config.output_path)
        fatalities = store.column("fatalities").to_pylist()
        assert fatalities == [99], (
            f"Expected revised fatalities=99, got {fatalities}"
        )

    def test_older_duplicate_does_not_replace(
        self, tmp_path: Path,
    ) -> None:
        """Re-consolidation with OLDER timestamp does not replace."""
        source_dir = tmp_path / "raw"

        # Run 1: event with fatalities=99, newer mtime
        path1 = _write_parquet(
            source_dir / "acled_2020_2025.parquet",
            [_base_event("SOM0001", fatalities=99)],
        )
        os.utime(path1, (2_000_000, 2_000_000))

        config = _make_config(tmp_path, source_dir)
        consolidate_acled(config)

        # Run 2: add file with OLD version (fatalities=0, earlier mtime)
        path2 = _write_parquet(
            source_dir / "acled_2025_2025.parquet",
            [_base_event("SOM0001", fatalities=0)],
        )
        os.utime(path2, (1_000_000, 1_000_000))

        consolidate_acled(config)

        store = read_store(config.output_path)
        fatalities = store.column("fatalities").to_pylist()
        assert fatalities == [99], (
            f"Store should keep newer fatalities=99, got {fatalities}"
        )

    def test_replacement_count_logged(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Cross-run replacement emits a log warning."""
        source_dir = tmp_path / "raw"

        path1 = _write_parquet(
            source_dir / "acled_2020_2025.parquet",
            [_base_event("SOM0001", fatalities=0)],
        )
        os.utime(path1, (1_000_000, 1_000_000))

        config = _make_config(tmp_path, source_dir)
        consolidate_acled(config)

        path2 = _write_parquet(
            source_dir / "acled_2025_2025.parquet",
            [_base_event("SOM0001", fatalities=99)],
        )
        os.utime(path2, (2_000_000, 2_000_000))

        with caplog.at_level(logging.WARNING):
            consolidate_acled(config)

        replacement_warnings = [
            r for r in caplog.records
            if "replac" in r.message.lower()
        ]
        assert len(replacement_warnings) >= 1, (
            "Expected a log warning about replaced events"
        )

    def test_count_conservation_with_replacements(
        self, tmp_path: Path,
    ) -> None:
        """Store count is correct after replacements + additions."""
        source_dir = tmp_path / "raw"

        # Run 1: 3 events (SOM0001, SOM0002, SOM0003)
        run1_events = [
            _base_event(f"SOM000{i}", fatalities=i)
            for i in range(1, 4)
        ]
        path1 = _write_parquet(
            source_dir / "acled_2020_2025.parquet",
            run1_events,
        )
        os.utime(path1, (1_000_000, 1_000_000))

        config = _make_config(tmp_path, source_dir)
        consolidate_acled(config)

        store = read_store(config.output_path)
        assert store.num_rows == 3

        # Run 2: revise SOM0001 + add new SOM0004
        run2_events = [
            _base_event("SOM0001", fatalities=99),
            _base_event("SOM0004", fatalities=10),
        ]
        path2 = _write_parquet(
            source_dir / "acled_2025_2025.parquet",
            run2_events,
        )
        os.utime(path2, (2_000_000, 2_000_000))

        consolidate_acled(config)

        store = read_store(config.output_path)
        assert store.num_rows == 4, (
            f"Expected 4 events (3 original - 1 replaced + "
            f"1 replaced + 1 new), got {store.num_rows}"
        )

        eids = set(store.column("event_id_cnty").to_pylist())
        assert eids == {"SOM0001", "SOM0002", "SOM0003", "SOM0004"}

    def test_mixed_new_and_revised_events(
        self, tmp_path: Path,
    ) -> None:
        """Run 2 correctly handles a mix of new, revised, and unchanged."""
        source_dir = tmp_path / "raw"

        # Run 1: A=0, B=0, C=0
        run1_events = [
            _base_event("SOM0001", fatalities=0),
            _base_event("SOM0002", fatalities=0),
            _base_event("SOM0003", fatalities=0),
        ]
        path1 = _write_parquet(
            source_dir / "acled_2020_2025.parquet",
            run1_events,
        )
        os.utime(path1, (1_000_000, 1_000_000))

        config = _make_config(tmp_path, source_dir)
        consolidate_acled(config)

        # Run 2: revise A=99, skip B (unchanged in run1 file),
        # add D=50
        run2_events = [
            _base_event("SOM0001", fatalities=99),
            _base_event("SOM0004", fatalities=50),
        ]
        path2 = _write_parquet(
            source_dir / "acled_2025_2025.parquet",
            run2_events,
        )
        os.utime(path2, (2_000_000, 2_000_000))

        consolidate_acled(config)

        store = read_store(config.output_path)
        eids = store.column("event_id_cnty").to_pylist()
        fats = store.column("fatalities").to_pylist()
        eid_to_fat = dict(zip(eids, fats, strict=True))

        assert len(eids) == 4, f"Expected 4 events, got {len(eids)}"
        assert eid_to_fat["SOM0001"] == 99, "Revised event"
        assert eid_to_fat["SOM0002"] == 0, "Unchanged event"
        assert eid_to_fat["SOM0003"] == 0, "Unchanged event"
        assert eid_to_fat["SOM0004"] == 50, "New event"
