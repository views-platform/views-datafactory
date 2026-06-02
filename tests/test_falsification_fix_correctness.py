"""Tests for the ACLED cache digest fix (issue #94).

The bug: _year_is_cached() compared compute_file_digest(snap_path)
against content_digest from the ledger. These are fundamentally
different for Parquet files — file digest hashes Parquet bytes,
content_digest hashes sorted event tuples as JSON. They never match,
causing every run to re-download all ACLED data.

The fix: _recompute_content_digest() reads the Parquet file back,
extracts digest fields, and recomputes content_digest using the
same algorithm as event_validation.py. This produces a value
comparable to the ledger's content_digest.
"""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from datafactory_harvester.sources.acled import (
    AcledConfig,
    _recompute_content_digest,
    _year_is_cached,
)
from datafactory_provenance import (
    append_ledger_entry,
    compute_content_digest,
)

# ---- Helpers ----


def _make_events(n: int = 5, id_start: int = 1) -> list[dict]:
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
    all_fields = sorted({k for ev in events for k in ev})
    columns = {f: [ev.get(f) for ev in events] for f in all_fields}
    pa_columns = {
        n: pa.array(v, from_pandas=True)
        for n, v in columns.items()
    }
    table = pa.table(pa_columns)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)
    return path


def _event_content_digest(events: list[dict]) -> str:
    """Replicate event_validation.py's content_digest computation."""
    digest_fields = ("event_id_cnty", "fatalities")
    digest_data = sorted(
        tuple(ev.get(f, 0) for f in digest_fields)
        for ev in events
    )
    return compute_content_digest(
        json.dumps(digest_data, sort_keys=True).encode()
    )


# ---- _recompute_content_digest ----


class TestRecomputeContentDigestGreen:

    def test_matches_original_content_digest(
        self, tmp_path: Path,
    ) -> None:
        """Recomputed digest matches event_validation's content_digest."""
        events = _make_events(10)
        snap = _write_parquet(
            tmp_path / "acled_2020_2020.parquet", events,
        )
        expected = _event_content_digest(events)
        actual = _recompute_content_digest(snap)
        assert actual == expected

    def test_deterministic_across_calls(
        self, tmp_path: Path,
    ) -> None:
        events = _make_events(5)
        snap = _write_parquet(
            tmp_path / "acled_2020_2020.parquet", events,
        )
        d1 = _recompute_content_digest(snap)
        d2 = _recompute_content_digest(snap)
        assert d1 == d2

    def test_handles_none_fatalities(
        self, tmp_path: Path,
    ) -> None:
        events = _make_events(3)
        events[1]["fatalities"] = None
        snap = _write_parquet(
            tmp_path / "acled_2020_2020.parquet", events,
        )
        expected = _event_content_digest(events)
        actual = _recompute_content_digest(snap)
        assert actual == expected

    def test_handles_zero_fatalities(
        self, tmp_path: Path,
    ) -> None:
        events = _make_events(3)
        for ev in events:
            ev["fatalities"] = 0
        snap = _write_parquet(
            tmp_path / "acled_2020_2020.parquet", events,
        )
        expected = _event_content_digest(events)
        actual = _recompute_content_digest(snap)
        assert actual == expected


class TestRecomputeContentDigestBeige:

    def test_missing_digest_column_returns_none(
        self, tmp_path: Path,
    ) -> None:
        """Parquet missing fatalities column returns None, not crash."""
        table = pa.table({
            "event_id_cnty": pa.array(["SOM0001"]),
            "country": pa.array(["Somalia"]),
        })
        path = tmp_path / "acled_2020_2020.parquet"
        pq.write_table(table, path)
        assert _recompute_content_digest(path) is None

    def test_corrupted_parquet_returns_none(
        self, tmp_path: Path,
    ) -> None:
        """Binary garbage returns None, not crash."""
        path = tmp_path / "acled_2020_2020.parquet"
        path.write_bytes(b"not a parquet file at all")
        assert _recompute_content_digest(path) is None

    def test_empty_parquet_returns_digest(
        self, tmp_path: Path,
    ) -> None:
        """Empty but valid Parquet with correct schema returns a digest."""
        table = pa.table({
            "event_id_cnty": pa.array([], type=pa.string()),
            "fatalities": pa.array([], type=pa.int64()),
        })
        path = tmp_path / "acled_2020_2020.parquet"
        pq.write_table(table, path)
        result = _recompute_content_digest(path)
        assert result is not None
        assert len(result) == 16


# ---- _year_is_cached (integration) ----


class TestYearIsCachedFixGreen:

    def test_matching_digest_returns_true(
        self, tmp_path: Path,
    ) -> None:
        """After fix, _year_is_cached returns True when data matches."""
        events = _make_events(5)
        data_dir = tmp_path / "raw"
        _write_parquet(
            data_dir / "acled_2020_2020.parquet", events,
        )
        content_digest = _event_content_digest(events)

        ledger_path = tmp_path / "prov" / "harvest.jsonl"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        append_ledger_entry(ledger_path, {
            "dataset": "acled",
            "version": "2020_2020",
            "outcome": "success",
            "content_digest": content_digest,
        })

        config = AcledConfig(
            start_year=2020,
            end_year=2020,
            data_dir=data_dir,
            ledger_path=ledger_path,
        )
        assert _year_is_cached(2020, config) is True

    def test_different_data_returns_false(
        self, tmp_path: Path,
    ) -> None:
        """Different data in file vs ledger returns False."""
        events_v1 = _make_events(5)
        events_v2 = _make_events(5, id_start=100)
        data_dir = tmp_path / "raw"
        _write_parquet(
            data_dir / "acled_2020_2020.parquet", events_v2,
        )
        content_digest_v1 = _event_content_digest(events_v1)

        ledger_path = tmp_path / "prov" / "harvest.jsonl"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        append_ledger_entry(ledger_path, {
            "dataset": "acled",
            "version": "2020_2020",
            "outcome": "success",
            "content_digest": content_digest_v1,
        })

        config = AcledConfig(
            start_year=2020,
            end_year=2020,
            data_dir=data_dir,
            ledger_path=ledger_path,
        )
        assert _year_is_cached(2020, config) is False

    def test_corrupted_file_returns_false(
        self, tmp_path: Path,
    ) -> None:
        """Corrupted Parquet file → cache miss, no crash."""
        data_dir = tmp_path / "raw"
        data_dir.mkdir(parents=True)
        (data_dir / "acled_2020_2020.parquet").write_bytes(
            b"corrupt"
        )

        ledger_path = tmp_path / "prov" / "harvest.jsonl"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        append_ledger_entry(ledger_path, {
            "dataset": "acled",
            "version": "2020_2020",
            "outcome": "success",
            "content_digest": "abcdef1234567890",
        })

        config = AcledConfig(
            start_year=2020,
            end_year=2020,
            data_dir=data_dir,
            ledger_path=ledger_path,
        )
        assert _year_is_cached(2020, config) is False
