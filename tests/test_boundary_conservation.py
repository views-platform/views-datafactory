"""Count conservation at consolidation and viewpoint boundaries
(C-258).

Extends ADR-040 conservation upstream: verifies that
input = output + discarded at every boundary where records are
filtered, deduplicated, or merged.
"""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from datafactory_consolidation.consolidators.ucdp import (
    UcdpConsolidationConfig,
)

# ---- ACLED Consolidation Helpers ----


def _make_acled_events(
    n: int = 5,
    id_start: int = 1,
) -> list[dict]:
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


def _write_acled_snapshot(
    path: Path, events: list[dict],
) -> Path:
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


# ---- UCDP Helpers ----


def _make_ucdp_event(
    event_id: int = 1,
    *,
    source_type: str = "annual",
    source_version: str = "25.1",
    date_start: str = "2023-06-15",
    date_end: str | None = None,
    date_prec: int = 1,
    best: int = 10,
) -> dict:
    return {
        "id": event_id,
        "country_id": 200,
        "country": "Sudan",
        "latitude": 4.0,
        "longitude": 31.5,
        "date_start": date_start,
        "date_end": date_end or date_start,
        "date_prec": date_prec,
        "best": best,
        "low": 5,
        "high": 15,
        "type_of_violence": 1,
        "where_prec": 1,
        "_source_type": source_type,
        "_source_version": source_version,
        "_ingested_at": "2026-03-21T10:00:00Z",
    }


def _write_consolidated(
    path: Path, events: list[dict],
) -> Path:
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


# ============================================================
# ACLED Consolidation Conservation
# ============================================================


class TestAcledConsolidationConservation:
    """input = output + discarded at ACLED consolidation."""

    def test_no_duplicates_preserves_all(
        self, tmp_path: Path,
    ) -> None:
        """Without duplicates, all events reach the store."""
        from datafactory_consolidation.consolidators.acled import (
            AcledConsolidationConfig,
            consolidate_acled,
        )

        events = _make_acled_events(10)
        source_dir = tmp_path / "raw"
        _write_acled_snapshot(
            source_dir / "acled_2020_2020.parquet", events,
        )

        config = AcledConsolidationConfig(
            source_dir=source_dir,
            output_path=tmp_path / "store" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )
        result = consolidate_acled(config)

        assert result.n_records_total == 10
        assert result.n_records_new == 10

        ledger = json.loads(
            (tmp_path / "prov" / "ledger.jsonl")
            .read_text()
            .strip()
        )
        assert ledger["n_records_concat"] == 10
        assert ledger["n_dedup_removed"] == 0

    def test_cross_file_dedup_conservation(
        self, tmp_path: Path,
    ) -> None:
        """Duplicates across files: concat = deduped + removed."""
        from datafactory_consolidation.consolidators.acled import (
            AcledConsolidationConfig,
            consolidate_acled,
        )

        source_dir = tmp_path / "raw"
        events_a = _make_acled_events(5)
        events_b = _make_acled_events(5)
        _write_acled_snapshot(
            source_dir / "acled_2020_2020.parquet", events_a,
        )
        _write_acled_snapshot(
            source_dir / "acled_2021_2021.parquet", events_b,
        )

        config = AcledConsolidationConfig(
            source_dir=source_dir,
            output_path=tmp_path / "store" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )
        result = consolidate_acled(config)

        assert result.n_records_total == 5

        ledger = json.loads(
            (tmp_path / "prov" / "ledger.jsonl")
            .read_text()
            .strip()
        )
        assert ledger["n_records_concat"] == 10
        assert ledger["n_dedup_removed"] == 5
        assert (
            ledger["n_records_concat"]
            == result.n_records_total + ledger["n_dedup_removed"]
        )

    def test_store_merge_conservation(
        self, tmp_path: Path,
    ) -> None:
        """Incremental merge: total = before + new."""
        from datafactory_consolidation.consolidators.acled import (
            AcledConsolidationConfig,
            consolidate_acled,
        )

        source_dir = tmp_path / "raw"
        events_1 = _make_acled_events(5)
        _write_acled_snapshot(
            source_dir / "acled_2020_2020.parquet", events_1,
        )

        config = AcledConsolidationConfig(
            source_dir=source_dir,
            output_path=tmp_path / "store" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )
        r1 = consolidate_acled(config)
        assert r1.n_records_total == 5

        events_2 = _make_acled_events(3, id_start=100)
        _write_acled_snapshot(
            source_dir / "acled_2021_2021.parquet", events_2,
        )

        consolidate_acled(config)

        ledger_lines = (
            (tmp_path / "prov" / "ledger.jsonl")
            .read_text()
            .strip()
            .split("\n")
        )
        last_entry = json.loads(ledger_lines[-1])
        assert last_entry["n_records_before"] == 5
        assert last_entry["n_records_new"] == 3
        assert last_entry["n_records_total"] == 8
        assert (
            last_entry["n_records_total"]
            == last_entry["n_records_before"]
            + last_entry["n_records_new"]
        )

    def test_dedup_returns_tuple(self) -> None:
        """_dedup_by_event_id returns (table, n_removed)."""
        from datafactory_consolidation.consolidators.acled import (
            _dedup_by_event_id,
        )

        table = pa.table({
            "event_id_cnty": ["A", "B", "C", "A"],
            "_harvest_timestamp": [
                "2026-01-01", "2026-01-01",
                "2026-01-01", "2026-02-01",
            ],
        })

        deduped, n_removed = _dedup_by_event_id(table)
        assert n_removed == 1
        assert deduped.num_rows == 3
        assert table.num_rows == deduped.num_rows + n_removed

    def test_no_duplicates_zero_removed(self) -> None:
        """When no duplicates exist, n_removed is 0."""
        from datafactory_consolidation.consolidators.acled import (
            _dedup_by_event_id,
        )

        table = pa.table({
            "event_id_cnty": ["A", "B", "C", "D", "E"],
            "_harvest_timestamp": ["2026-01-01"] * 5,
        })

        deduped, n_removed = _dedup_by_event_id(table)
        assert n_removed == 0
        assert deduped.num_rows == 5


# ============================================================
# UCDP Consolidation Conservation
# ============================================================


def _ucdp_config(
    tmp_path: Path,
    annual_dir: Path | None = None,
) -> UcdpConsolidationConfig:
    return UcdpConsolidationConfig(
        annual_dir=annual_dir or tmp_path / "annual",
        candidate_dir=tmp_path / "candidate",
        dot9_dir=tmp_path / "dot9",
        annual_ledger_path=(
            tmp_path / "prov_annual" / "ledger.jsonl"
        ),
        candidate_ledger_path=(
            tmp_path / "prov_cand" / "ledger.jsonl"
        ),
        dot9_ledger_path=(
            tmp_path / "prov_dot9" / "ledger.jsonl"
        ),
        output_path=tmp_path / "store" / "out.parquet",
        ledger_path=tmp_path / "prov" / "ledger.jsonl",
    )


def _make_ucdp_raw_events(
    n: int = 5, id_start: int = 1,
) -> list[dict]:
    """Raw UCDP events (no metadata columns)."""
    return [
        {
            "id": id_start + i,
            "country_id": 200,
            "country": "Sudan",
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


class TestUcdpConsolidationConservation:
    """Ledger records dedup counts at UCDP consolidation."""

    def test_dedup_filtered_in_ledger(
        self, tmp_path: Path,
    ) -> None:
        """Ledger includes n_records_raw and
        n_records_dedup_filtered."""
        from datafactory_consolidation.consolidators.ucdp import (
            consolidate_ucdp,
        )

        annual_dir = tmp_path / "annual"
        events = _make_ucdp_raw_events(5)
        _write_consolidated(
            annual_dir
            / "ucdp_ged_v25.1_1989_2024.parquet",
            events,
        )

        config = _ucdp_config(
            tmp_path, annual_dir=annual_dir,
        )
        consolidate_ucdp(config)

        ledger = json.loads(
            (tmp_path / "prov" / "ledger.jsonl")
            .read_text()
            .strip()
        )
        assert "n_records_raw" in ledger
        assert "n_records_dedup_filtered" in ledger
        assert ledger["n_records_raw"] == 5
        assert ledger["n_records_dedup_filtered"] == 0
        assert (
            ledger["n_records_raw"]
            == ledger["n_records_new"]
            + ledger["n_records_dedup_filtered"]
        )

    def test_incremental_dedup_counted(
        self, tmp_path: Path,
    ) -> None:
        """Re-ingesting same data: dedup_filtered = raw count."""
        from datafactory_consolidation.consolidators.ucdp import (
            consolidate_ucdp,
        )

        annual_dir = tmp_path / "annual"
        events = _make_ucdp_raw_events(5)
        _write_consolidated(
            annual_dir
            / "ucdp_ged_v25.1_1989_2024.parquet",
            events,
        )

        config = _ucdp_config(
            tmp_path, annual_dir=annual_dir,
        )

        consolidate_ucdp(config)
        consolidate_ucdp(config)

        ledger_lines = (
            (tmp_path / "prov" / "ledger.jsonl")
            .read_text()
            .strip()
            .split("\n")
        )
        second = json.loads(ledger_lines[-1])
        assert second["n_records_raw"] == 5
        assert second["n_records_dedup_filtered"] == 5
        assert second["n_records_new"] == 0


# ============================================================
# ACLED Viewpoint Conservation
# ============================================================


class TestAcledViewpointConservation:
    """input = output + filtered at ACLED viewpoint."""

    def _make_store(
        self, path: Path, n: int = 10,
        event_types: list[str] | None = None,
    ) -> Path:
        if event_types is None:
            event_types = ["Battles", "Protests", "Riots"]
        events = {
            "event_id_cnty": [
                f"SOM{i:04d}" for i in range(n)
            ],
            "event_date": [
                f"2020-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}"
                for i in range(n)
            ],
            "event_type": [
                event_types[i % len(event_types)]
                for i in range(n)
            ],
            "sub_event_type": ["Armed clash"] * n,
            "actor1": [f"Group A{i}" for i in range(n)],
            "actor2": [f"Group B{i}" for i in range(n)],
            "country": ["Somalia"] * n,
            "admin1": ["Banadir"] * n,
            "latitude": [2.0 + i * 0.1 for i in range(n)],
            "longitude": [45.0 + i * 0.1 for i in range(n)],
            "fatalities": [i * 3 for i in range(n)],
            "notes": [f"Test event {i}" for i in range(n)],
            "source": ["Test"] * n,
            "source_scale": ["National"] * n,
            "_source_type": ["acled"] * n,
            "_source_version": ["2020_2020"] * n,
            "_ingested_at": ["2026-01-01T00:00:00Z"] * n,
            "_harvest_digest": ["abc123"] * n,
            "_harvest_timestamp": ["2026-01-01T00:00:00Z"] * n,
        }
        table = pa.table(events)
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, path)
        return path

    def test_no_filter_all_preserved(
        self, tmp_path: Path,
    ) -> None:
        """Without event_type_filter, all events pass through."""
        from datafactory_viewpoint.builders.acled_v1 import (
            AcledViewpointConfig,
            build_acled_v1,
        )

        store = tmp_path / "store" / "acled.parquet"
        self._make_store(store, n=15)

        config = AcledViewpointConfig(
            consolidated_path=store,
            output_path=tmp_path / "vp" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )
        result = build_acled_v1(config)

        assert result.n_events_input == 15
        assert result.n_events_output == 15
        assert result.n_filtered == 0
        assert (
            result.n_events_input
            == result.n_events_output + result.n_filtered
        )

    def test_filter_conservation(
        self, tmp_path: Path,
    ) -> None:
        """With event_type_filter: input = output + filtered."""
        from datafactory_viewpoint.builders.acled_v1 import (
            AcledViewpointConfig,
            build_acled_v1,
        )

        store = tmp_path / "store" / "acled.parquet"
        self._make_store(
            store, n=30,
            event_types=["Battles", "Protests", "Riots"],
        )

        config = AcledViewpointConfig(
            consolidated_path=store,
            output_path=tmp_path / "vp" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
            event_type_filter=["Battles"],
        )
        result = build_acled_v1(config)

        assert result.n_events_input == 30
        assert result.n_events_output == 10
        assert result.n_filtered == 20
        assert (
            result.n_events_input
            == result.n_events_output + result.n_filtered
        )

    def test_ledger_records_counts(
        self, tmp_path: Path,
    ) -> None:
        """Ledger entry contains conservation-auditable fields."""
        from datafactory_viewpoint.builders.acled_v1 import (
            AcledViewpointConfig,
            build_acled_v1,
        )

        store = tmp_path / "store" / "acled.parquet"
        self._make_store(
            store, n=12,
            event_types=["Battles", "Protests"],
        )

        config = AcledViewpointConfig(
            consolidated_path=store,
            output_path=tmp_path / "vp" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
            event_type_filter=["Battles"],
        )
        build_acled_v1(config)

        ledger = json.loads(
            (tmp_path / "prov" / "ledger.jsonl")
            .read_text()
            .strip()
        )
        assert (
            ledger["n_events_input"]
            == ledger["n_events_output"] + ledger["n_filtered"]
        )


# ============================================================
# UCDP Viewpoint Conservation
# ============================================================


class TestUcdpViewpointConservation:
    """Conservation at UCDP viewpoint: stale filtering +
    survivorship + distribution + config filtering."""

    def test_no_stale_all_preserved(
        self, tmp_path: Path,
    ) -> None:
        """Without stale filtering, n_stale = 0."""
        from datafactory_viewpoint.builders.ucdp_v1 import (
            ViewpointConfig,
            build_ucdp_v1,
        )

        store = tmp_path / "store" / "ucdp.parquet"
        events = [
            _make_ucdp_event(i, source_type="annual")
            for i in range(1, 6)
        ]
        _write_consolidated(store, events)

        config = ViewpointConfig(
            consolidated_path=store,
            output_path=tmp_path / "vp" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
            filter_stale_versions=False,
        )
        result = build_ucdp_v1(config)

        assert result.n_events_input == 5
        assert result.n_events_output == 5
        assert result.n_filtered == 0

        ledger = json.loads(
            (tmp_path / "prov" / "ledger.jsonl")
            .read_text()
            .strip()
        )
        assert ledger["n_events_read"] == 5
        assert ledger["n_stale_filtered"] == 0

    def test_stale_filtering_conservation(
        self, tmp_path: Path,
    ) -> None:
        """read = input + stale when stale versions filtered."""
        from datafactory_viewpoint.builders.ucdp_v1 import (
            ViewpointConfig,
            build_ucdp_v1,
        )

        store = tmp_path / "store" / "ucdp.parquet"
        events = [
            _make_ucdp_event(
                1, source_type="annual",
                date_start="2023-06-15",
            ),
            _make_ucdp_event(
                2, source_type="annual",
                date_start="2023-07-15",
            ),
            _make_ucdp_event(
                3,
                source_type="dot9",
                source_version="25.0.6",
                date_start="2023-08-15",
            ),
            _make_ucdp_event(
                4,
                source_type="dot9",
                source_version="25.0.9",
                date_start="2023-09-15",
            ),
        ]
        _write_consolidated(store, events)

        config = ViewpointConfig(
            consolidated_path=store,
            output_path=tmp_path / "vp" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
            filter_stale_versions=True,
        )
        build_ucdp_v1(config)

        ledger = json.loads(
            (tmp_path / "prov" / "ledger.jsonl")
            .read_text()
            .strip()
        )
        assert ledger["n_events_read"] == 4
        n_stale = ledger["n_stale_filtered"]
        assert (
            ledger["n_events_read"]
            == ledger["n_events_input"] + n_stale
        )

    def test_survivorship_discarded_in_ledger(
        self, tmp_path: Path,
    ) -> None:
        """Groups with multiple versions: survivorship discards
        are tracked in ledger."""
        from datafactory_viewpoint.builders.ucdp_v1 import (
            ViewpointConfig,
            build_ucdp_v1,
        )

        store = tmp_path / "store" / "ucdp.parquet"
        events = [
            _make_ucdp_event(
                1, source_type="annual",
                source_version="25.1",
            ),
            _make_ucdp_event(
                1, source_type="candidate",
                source_version="250301",
            ),
            _make_ucdp_event(
                2, source_type="annual",
                source_version="25.1",
            ),
        ]
        _write_consolidated(store, events)

        config = ViewpointConfig(
            consolidated_path=store,
            output_path=tmp_path / "vp" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
            filter_stale_versions=False,
        )
        build_ucdp_v1(config)

        ledger = json.loads(
            (tmp_path / "prov" / "ledger.jsonl")
            .read_text()
            .strip()
        )
        assert ledger["n_groups"] == 2
        assert ledger["n_survivorship_discarded"] == 1
        assert (
            ledger["n_events_input"]
            == ledger["n_groups"]
            + ledger["n_survivorship_discarded"]
        )

    def test_full_chain_conservation(
        self, tmp_path: Path,
    ) -> None:
        """Complete chain: read -> stale -> groups ->
        output + filtered."""
        from datafactory_viewpoint.builders.ucdp_v1 import (
            ViewpointConfig,
            build_ucdp_v1,
        )

        store = tmp_path / "store" / "ucdp.parquet"
        events = [
            _make_ucdp_event(
                1, source_type="annual",
                date_start="2023-06-15",
                best=10,
            ),
            _make_ucdp_event(
                1, source_type="candidate",
                source_version="250301",
                date_start="2023-06-15",
                best=12,
            ),
            _make_ucdp_event(
                2, source_type="annual",
                date_start="2023-07-15",
                best=5,
            ),
            _make_ucdp_event(
                3, source_type="annual",
                date_start="2023-08-15",
                best=8,
            ),
        ]
        _write_consolidated(store, events)

        config = ViewpointConfig(
            consolidated_path=store,
            output_path=tmp_path / "vp" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
            filter_stale_versions=False,
        )
        result = build_ucdp_v1(config)

        ledger = json.loads(
            (tmp_path / "prov" / "ledger.jsonl")
            .read_text()
            .strip()
        )

        assert (
            ledger["n_events_read"]
            == ledger["n_events_input"]
            + ledger["n_stale_filtered"]
        )
        assert (
            ledger["n_events_input"]
            == ledger["n_groups"]
            + ledger["n_survivorship_discarded"]
        )
        assert (
            result.n_events_output + result.n_filtered
            >= ledger["n_groups"]
        )
