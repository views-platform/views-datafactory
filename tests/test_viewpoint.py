"""Tests for datafactory_viewpoint — survivorship, distribution, builder.

Uses synthetic consolidated events with metadata columns.
No network access needed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from datafactory_viewpoint.builders.ucdp_v1 import build_ucdp_v1
from datafactory_viewpoint.survivorship import annual_wins, get_survivorship
from datafactory_viewpoint.temporal_distribution import (
    even_split,
    get_distribution,
)
from datafactory_viewpoint.viewpoint_config import ViewpointConfig
from datafactory_viewpoint.viewpoint_result import ViewpointResult

# ---- Helpers ----


def _make_consolidated_event(
    event_id: int = 1,
    *,
    source_type: str = "annual",
    source_version: str = "25.1",
    date_start: str = "2023-06-15",
    date_end: str | None = None,
    date_prec: int = 1,
    best: int = 10,
    low: int = 5,
    high: int = 15,
    latitude: float = 4.0,
    longitude: float = 31.5,
    priogrid_gid: int | None = None,
) -> dict:
    """Create a single consolidated event dict with metadata."""
    ev: dict = {
        "id": event_id,
        "country_id": 200,
        "country": "Sudan",
        "latitude": latitude,
        "longitude": longitude,
        "date_start": date_start,
        "date_end": date_end or date_start,
        "date_prec": date_prec,
        "best": best,
        "low": low,
        "high": high,
        "type_of_violence": 1,
        "where_prec": 1,
        "_source_type": source_type,
        "_source_version": source_version,
        "_ingested_at": "2026-03-21T10:00:00Z",
    }
    if priogrid_gid is not None:
        ev["priogrid_gid"] = priogrid_gid
    return ev


def _write_consolidated(path: Path, events: list[dict]) -> Path:
    """Write a consolidated store Parquet from event dicts."""
    all_fields = sorted({k for ev in events for k in ev})
    columns = {f: [ev.get(f) for ev in events] for f in all_fields}
    pa_columns = {
        n: pa.array(v, from_pandas=True) for n, v in columns.items()
    }
    table = pa.table(pa_columns)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)
    return path


def _config(
    tmp_path: Path, consolidated_path: Path
) -> ViewpointConfig:
    """Build a test config."""
    return ViewpointConfig(
        consolidated_path=consolidated_path,
        output_path=tmp_path / "viewpoint" / "output.parquet",
        ledger_path=tmp_path / "provenance" / "ledger.jsonl",
    )


# ---- Survivorship: Green ----


class TestSurvivorshipGreen:

    def test_annual_wins_picks_annual(self) -> None:
        versions = [
            _make_consolidated_event(
                source_type="candidate", source_version="25.0.3"
            ),
            _make_consolidated_event(
                source_type="annual", source_version="25.1"
            ),
        ]
        winner = annual_wins(versions)
        assert winner["_source_type"] == "annual"

    def test_annual_wins_picks_latest_candidate(self) -> None:
        versions = [
            _make_consolidated_event(
                source_type="candidate", source_version="25.0.1"
            ),
            _make_consolidated_event(
                source_type="candidate", source_version="25.0.12"
            ),
            _make_consolidated_event(
                source_type="candidate", source_version="25.0.3"
            ),
        ]
        winner = annual_wins(versions)
        assert winner["_source_version"] == "25.0.12"

    def test_single_version_returns_it(self) -> None:
        versions = [
            _make_consolidated_event(
                source_type="annual", source_version="25.1"
            ),
        ]
        winner = annual_wins(versions)
        assert winner["_source_type"] == "annual"

    def test_get_survivorship_valid(self) -> None:
        fn = get_survivorship("annual_wins")
        assert fn is annual_wins

    def test_get_survivorship_invalid(self) -> None:
        with pytest.raises(KeyError, match="Unknown"):
            get_survivorship("nonexistent")


# ---- Temporal Distribution: Green ----


class TestTemporalDistributionGreen:

    def test_even_split_non_summary(self) -> None:
        event = _make_consolidated_event(
            date_prec=1,
            date_start="2023-06-15",
            date_end="2023-06-15",
        )
        rows = even_split(event)
        assert len(rows) == 1
        assert rows[0]["date_month"] == "2023-06-01"
        assert rows[0]["best"] == 10  # unchanged

    def test_even_split_summary_3_months(self) -> None:
        event = _make_consolidated_event(
            date_prec=5,
            date_start="2023-01-15",
            date_end="2023-03-31",
            best=300,
            low=150,
            high=450,
        )
        rows = even_split(event)
        assert len(rows) == 3
        assert rows[0]["date_month"] == "2023-01-01"
        assert rows[1]["date_month"] == "2023-02-01"
        assert rows[2]["date_month"] == "2023-03-01"
        assert rows[0]["best"] == 100.0
        assert rows[1]["low"] == 50.0
        assert rows[2]["high"] == 150.0

    def test_even_split_preserves_fields(self) -> None:
        event = _make_consolidated_event(
            date_prec=5,
            date_start="2023-01-01",
            date_end="2023-02-28",
            best=100,
        )
        rows = even_split(event)
        for row in rows:
            assert row["id"] == 1
            assert row["country"] == "Sudan"
            assert row["type_of_violence"] == 1

    def test_even_split_uses_date_end_for_non_summary(self) -> None:
        """Non-summary events get date_month from date_end."""
        event = _make_consolidated_event(
            date_prec=2,
            date_start="2023-06-01",
            date_end="2023-07-15",
        )
        rows = even_split(event)
        assert len(rows) == 1
        assert rows[0]["date_month"] == "2023-07-01"

    def test_get_distribution_valid(self) -> None:
        fn = get_distribution("even_split")
        assert fn is even_split

    def test_get_distribution_invalid(self) -> None:
        with pytest.raises(KeyError, match="Unknown"):
            get_distribution("nonexistent")


class TestTemporalDistributionRed:

    def test_summary_missing_date_end_raises(self) -> None:
        event = _make_consolidated_event(
            date_prec=5,
            date_start="2023-01-01",
        )
        event["date_end"] = None
        event["date_start"] = None
        with pytest.raises(ValueError, match="missing date_start"):
            even_split(event)

    def test_summary_zero_months_raises(self) -> None:
        event = _make_consolidated_event(
            date_prec=5,
            date_start="2023-03-15",
            date_end="2023-02-01",
        )
        with pytest.raises(ValueError, match="zero months"):
            even_split(event)


# ---- ViewpointConfig: Green ----


class TestViewpointConfigGreen:

    def test_defaults(self, tmp_path: Path) -> None:
        cfg = ViewpointConfig(
            consolidated_path=tmp_path / "store.parquet"
        )
        assert cfg.survivorship_strategy == "annual_wins"
        assert cfg.distribution_strategy == "even_split"
        assert cfg.version == "v1"

    def test_frozen(self, tmp_path: Path) -> None:
        cfg = ViewpointConfig(
            consolidated_path=tmp_path / "store.parquet"
        )
        with pytest.raises(AttributeError):
            cfg.version = "v2"  # type: ignore[misc]


# ---- Build UCDP v1: Green ----


class TestBuildUcdpV1Green:

    def test_produces_output_parquet(self, tmp_path: Path) -> None:
        events = [_make_consolidated_event(event_id=i) for i in range(5)]
        store = _write_consolidated(
            tmp_path / "store.parquet", events
        )
        cfg = _config(tmp_path, store)

        result = build_ucdp_v1(cfg)

        assert isinstance(result, ViewpointResult)
        assert result.output_path.exists()
        assert result.n_events_output == 5

    def test_date_month_column_present(self, tmp_path: Path) -> None:
        events = [_make_consolidated_event()]
        store = _write_consolidated(
            tmp_path / "store.parquet", events
        )
        cfg = _config(tmp_path, store)

        build_ucdp_v1(cfg)

        table = pq.read_table(cfg.output_path)
        assert "date_month" in table.column_names

    def test_survivorship_applied(self, tmp_path: Path) -> None:
        """Annual + candidate for same id → only annual in output."""
        events = [
            _make_consolidated_event(
                event_id=42,
                source_type="annual",
                source_version="25.1",
                best=10,
            ),
            _make_consolidated_event(
                event_id=42,
                source_type="candidate",
                source_version="25.0.6",
                best=15,
            ),
        ]
        store = _write_consolidated(
            tmp_path / "store.parquet", events
        )
        cfg = _config(tmp_path, store)

        result = build_ucdp_v1(cfg)

        assert result.n_events_input == 2
        assert result.n_events_output == 1

        table = pq.read_table(cfg.output_path)
        assert table.num_rows == 1
        # Annual version won — best=10, not 15
        assert table.column("best").to_pylist()[0] == 10

    def test_summary_events_expanded(self, tmp_path: Path) -> None:
        events = [
            _make_consolidated_event(
                event_id=1,
                date_prec=5,
                date_start="2023-01-01",
                date_end="2023-03-31",
                best=300,
            ),
        ]
        store = _write_consolidated(
            tmp_path / "store.parquet", events
        )
        cfg = _config(tmp_path, store)

        result = build_ucdp_v1(cfg)

        assert result.n_events_output == 3
        assert result.n_summary_expanded == 1

        table = pq.read_table(cfg.output_path)
        months = sorted(table.column("date_month").to_pylist())
        assert months == ["2023-01-01", "2023-02-01", "2023-03-01"]

    def test_provenance_recorded(self, tmp_path: Path) -> None:
        events = [_make_consolidated_event()]
        store = _write_consolidated(
            tmp_path / "store.parquet", events
        )
        cfg = _config(tmp_path, store)

        build_ucdp_v1(cfg)

        assert cfg.ledger_path.exists()
        entry = json.loads(
            cfg.ledger_path.read_text().strip().splitlines()[-1]
        )
        assert entry["dataset"] == "ucdp_viewpoint"
        assert entry["version"] == "v1"
        assert "output_digest" in entry
        assert entry["n_events_output"] == 1

    def test_metadata_columns_stripped(self, tmp_path: Path) -> None:
        """Consolidation metadata should not appear in output."""
        events = [_make_consolidated_event()]
        store = _write_consolidated(
            tmp_path / "store.parquet", events
        )
        cfg = _config(tmp_path, store)

        build_ucdp_v1(cfg)

        table = pq.read_table(cfg.output_path)
        for col in ("_source_type", "_source_version", "_ingested_at"):
            assert col not in table.column_names


# ---- Build UCDP v1: Beige ----


class TestBuildUcdpV1Beige:

    def test_annual_only(self, tmp_path: Path) -> None:
        """No candidate data — all annual records returned."""
        events = [
            _make_consolidated_event(
                event_id=i, source_type="annual"
            )
            for i in range(3)
        ]
        store = _write_consolidated(
            tmp_path / "store.parquet", events
        )
        cfg = _config(tmp_path, store)

        result = build_ucdp_v1(cfg)
        assert result.n_events_output == 3


# ---- Build UCDP v1: Red ----


class TestBuildUcdpV1Red:

    def test_missing_store_raises(self, tmp_path: Path) -> None:
        cfg = ViewpointConfig(
            consolidated_path=tmp_path / "nonexistent.parquet",
            output_path=tmp_path / "out.parquet",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        with pytest.raises(FileNotFoundError, match="not found"):
            build_ucdp_v1(cfg)

    def test_no_config_no_path_raises(self) -> None:
        with pytest.raises(ValueError, match="config or consolidated_path"):
            build_ucdp_v1(None)

    def test_empty_store_raises(self, tmp_path: Path) -> None:
        # Write empty Parquet with correct schema
        table = pa.table({
            "id": pa.array([], type=pa.int64()),
            "_source_type": pa.array([], type=pa.string()),
            "_source_version": pa.array([], type=pa.string()),
            "_ingested_at": pa.array([], type=pa.string()),
        })
        path = tmp_path / "empty.parquet"
        pq.write_table(table, path)

        cfg = ViewpointConfig(
            consolidated_path=path,
            output_path=tmp_path / "out.parquet",
            ledger_path=tmp_path / "ledger.jsonl",
        )
        with pytest.raises(ValueError, match="empty"):
            build_ucdp_v1(cfg)


# ---- Registry ----


class TestBuilderRegistration:

    def test_registered_in_builders(self) -> None:
        import datafactory_viewpoint.builders.ucdp_v1  # noqa: F401
        from datafactory_viewpoint.builders import list_builders

        assert "ucdp_v1" in list_builders()
