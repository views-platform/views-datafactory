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
from datafactory_viewpoint.survivorship import (
    _parse_version,
    annual_wins,
    dot9_wins,
    get_survivorship,
)
from datafactory_viewpoint.temporal_distribution import (
    _validate_date_str,
    ceil_split,
    even_split,
    get_distribution,
)
from datafactory_viewpoint.viewpoint_config import ViewpointConfig

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

    def test_dot9_wins_picks_annual_over_dot9(self) -> None:
        versions = [
            _make_consolidated_event(
                source_type="dot9", source_version="25.9.11"
            ),
            _make_consolidated_event(
                source_type="annual", source_version="25.1"
            ),
        ]
        winner = dot9_wins(versions)
        assert winner["_source_type"] == "annual"

    def test_dot9_wins_picks_dot9_over_candidate(self) -> None:
        versions = [
            _make_consolidated_event(
                source_type="candidate", source_version="25.0.6"
            ),
            _make_consolidated_event(
                source_type="dot9", source_version="25.9.6"
            ),
        ]
        winner = dot9_wins(versions)
        assert winner["_source_type"] == "dot9"

    def test_dot9_wins_picks_latest_dot9(self) -> None:
        versions = [
            _make_consolidated_event(
                source_type="dot9", source_version="25.9.1"
            ),
            _make_consolidated_event(
                source_type="dot9", source_version="25.9.11"
            ),
        ]
        winner = dot9_wins(versions)
        assert winner["_source_version"] == "25.9.11"

    def test_dot9_wins_falls_back_to_candidate(self) -> None:
        versions = [
            _make_consolidated_event(
                source_type="candidate",
                source_version="25.0.3",
            ),
            _make_consolidated_event(
                source_type="candidate",
                source_version="25.0.11",
            ),
        ]
        winner = dot9_wins(versions)
        assert winner["_source_version"] == "25.0.11"

    def test_get_dot9_wins_by_name(self) -> None:
        fn = get_survivorship("dot9_wins")
        assert fn is dot9_wins


# ---- Version Parsing: C-106 ----


class TestParseVersionGreen:

    def test_dotted_integers(self) -> None:
        assert _parse_version("25.1") == (25, 1)

    def test_three_part(self) -> None:
        assert _parse_version("25.0.12") == (25, 0, 12)

    def test_single_integer(self) -> None:
        assert _parse_version("25") == (25,)


class TestParseVersionRed:

    def test_non_numeric_returns_zero(self) -> None:
        assert _parse_version("25.1-beta") == (0,)

    def test_empty_string_returns_zero(self) -> None:
        assert _parse_version("") == (0,)

    def test_non_numeric_sorts_below_numeric(self) -> None:
        """Non-numeric versions are never preferred."""
        assert _parse_version("beta") < _parse_version("1.0")

    def test_survivorship_with_non_numeric(self) -> None:
        """annual_wins handles non-numeric version gracefully."""
        versions = [
            _make_consolidated_event(
                source_type="candidate",
                source_version="25.1-beta",
            ),
            _make_consolidated_event(
                source_type="candidate",
                source_version="25.0.3",
            ),
        ]
        winner = annual_wins(versions)
        assert winner["_source_version"] == "25.0.3"


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


# ---- Date Validation: C-104 ----


class TestDateValidation:

    def test_valid_date_passes(self) -> None:
        assert _validate_date_str("2023-03-15") == "2023-03-15"

    def test_iso_datetime_rejected(self) -> None:
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            _validate_date_str("2023-03-15T00:00:00")

    def test_slash_format_rejected(self) -> None:
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            _validate_date_str("2023/03/15")

    def test_missing_leading_zero_rejected(self) -> None:
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            _validate_date_str("2023-3-15")

    def test_month_first_day_rejects_bad_format(self) -> None:
        from datafactory_viewpoint.temporal_distribution import (
            _month_first_day,
        )

        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            _month_first_day("2023-03-15T12:00:00")

    def test_months_between_rejects_bad_format(self) -> None:
        from datafactory_viewpoint.temporal_distribution import (
            _months_between,
        )

        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            _months_between("2023/01/15", "2023-03-31")


# ---- Ceil Split (Production Parity): Green ----


class TestCeilSplitGreen:

    def test_non_summary_single_row(self) -> None:
        """best=0 → not summary, single row returned."""
        event = _make_consolidated_event(
            date_prec=1,
            date_start="2023-06-15",
            date_end="2023-06-15",
            best=0,
        )
        rows = ceil_split(event)
        assert len(rows) == 1
        assert rows[0]["date_month"] == "2023-06-01"

    def test_best_zero_multi_month_not_summary(
        self,
    ) -> None:
        """best=0, span=3 → NOT detected as summary (best < span).
        Returns single row from date_end (C-59).
        """
        event = _make_consolidated_event(
            date_prec=1,
            date_start="2023-01-15",
            date_end="2023-03-31",
            best=0,
            low=0,
            high=0,
        )
        rows = ceil_split(event)
        # best=0 < span=3 → not summary → single row
        assert len(rows) == 1
        assert rows[0]["best"] == 0

    def test_summary_3_months_ceil(self) -> None:
        """best=7, span=3 → 3 rows with ceil(7/3)=3 each."""
        event = _make_consolidated_event(
            date_prec=1,  # NOT date_prec=5 — production ignores it
            date_start="2023-01-15",
            date_end="2023-03-31",
            best=7,
            low=4,
            high=10,
        )
        rows = ceil_split(event)
        assert len(rows) == 3
        assert rows[0]["best"] == 3  # ceil(7/3) = 3
        assert rows[0]["low"] == 2   # ceil(4/3) = 2
        assert rows[0]["high"] == 4  # ceil(10/3) = 4

    def test_exact_divisible(self) -> None:
        """best=300, span=3 → 100 each (ceil agrees with exact)."""
        event = _make_consolidated_event(
            date_start="2023-01-01",
            date_end="2023-03-31",
            best=300,
            low=150,
            high=450,
        )
        rows = ceil_split(event)
        assert len(rows) == 3
        assert rows[0]["best"] == 100
        assert rows[1]["low"] == 50
        assert rows[2]["high"] == 150

    def test_date_prec5_but_zero_best_not_summary(self) -> None:
        """Production detection: date_prec=5 but best=0 → NOT summary."""
        event = _make_consolidated_event(
            date_prec=5,
            date_start="2023-01-01",
            date_end="2023-03-31",
            best=0,
        )
        rows = ceil_split(event)
        assert len(rows) == 1  # NOT expanded — best=0 fails detection

    def test_non_prec5_multi_month_is_summary(self) -> None:
        """date_prec=1 but span>1 and best>=span → IS summary."""
        event = _make_consolidated_event(
            date_prec=1,
            date_start="2023-01-01",
            date_end="2023-03-31",
            best=10,
        )
        rows = ceil_split(event)
        assert len(rows) == 3  # IS expanded — meets production criteria

    def test_best_less_than_span_not_summary(self) -> None:
        """best=2, span=3 → not summary (best < span)."""
        event = _make_consolidated_event(
            date_start="2023-01-01",
            date_end="2023-03-31",
            best=2,
        )
        rows = ceil_split(event)
        assert len(rows) == 1  # NOT expanded — best < span

    def test_get_ceil_split_by_name(self) -> None:
        fn = get_distribution("ceil_split")
        assert fn is ceil_split


# ---- ViewpointConfig: Green ----


class TestViewpointConfigGreen:

    def test_defaults(self, tmp_path: Path) -> None:
        cfg = ViewpointConfig(
            consolidated_path=tmp_path / "store.parquet"
        )
        assert cfg.survivorship_strategy == "annual_wins"
        assert cfg.distribution_strategy == "even_split"
        assert cfg.version == "custom"

    def test_frozen(self, tmp_path: Path) -> None:
        cfg = ViewpointConfig(
            consolidated_path=tmp_path / "store.parquet"
        )
        with pytest.raises(AttributeError):
            cfg.version = "v2"  # type: ignore[misc]


# ---- ViewpointConfig: Beige ----


class TestViewpointConfigBeige:

    def test_invalid_survivorship_strategy(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(ValueError, match="survivorship"):
            ViewpointConfig(
                consolidated_path=tmp_path / "store.parquet",
                survivorship_strategy="nonexistent",
            )

    def test_invalid_distribution_strategy(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(ValueError, match="distribution"):
            ViewpointConfig(
                consolidated_path=tmp_path / "store.parquet",
                distribution_strategy="nonexistent",
            )

    def test_empty_version(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="version"):
            ViewpointConfig(
                consolidated_path=tmp_path / "store.parquet",
                version="",
            )


# ---- Build UCDP v1: Green ----


class TestBuildUcdpV1Green:

    def test_produces_output_parquet(self, tmp_path: Path) -> None:
        events = [_make_consolidated_event(event_id=i) for i in range(5)]
        store = _write_consolidated(
            tmp_path / "store.parquet", events
        )
        cfg = _config(tmp_path, store)

        result = build_ucdp_v1(cfg)

        assert result.output_path.exists()
        assert result.n_events_output == 5
        assert len(result.output_digest) == 16

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
        assert entry["version"] == "custom"
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


# ---- Filtering: Green ----


class TestFilteringGreen:

    def test_no_filters_by_default(self, tmp_path: Path) -> None:
        """Default config has no filters — all events kept."""
        events = [
            _make_consolidated_event(
                event_id=1, priogrid_gid=0,
            ),
            _make_consolidated_event(
                event_id=2, priogrid_gid=100,
            ),
        ]
        store = _write_consolidated(
            tmp_path / "store.parquet", events
        )
        cfg = _config(tmp_path, store)

        result = build_ucdp_v1(cfg)
        assert result.n_events_output == 2
        assert result.n_filtered == 0

    def test_filter_priogrid_gid(self, tmp_path: Path) -> None:
        events = [
            _make_consolidated_event(
                event_id=1, priogrid_gid=0,
            ),
            _make_consolidated_event(
                event_id=2, priogrid_gid=100,
            ),
        ]
        store = _write_consolidated(
            tmp_path / "store.parquet", events
        )
        cfg = ViewpointConfig(
            consolidated_path=store,
            output_path=tmp_path / "vp" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
            min_priogrid_gid=1,
        )

        result = build_ucdp_v1(cfg)
        assert result.n_events_output == 1
        assert result.n_filtered == 1

    def test_filter_type_of_violence(
        self, tmp_path: Path
    ) -> None:
        events = [
            _make_consolidated_event(event_id=i)
            for i in range(3)
        ]
        # Manually set type_of_violence
        events[0]["type_of_violence"] = 1
        events[1]["type_of_violence"] = 3
        events[2]["type_of_violence"] = 4

        store = _write_consolidated(
            tmp_path / "store.parquet", events
        )
        cfg = ViewpointConfig(
            consolidated_path=store,
            output_path=tmp_path / "vp" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
            max_type_of_violence=3,
        )

        result = build_ucdp_v1(cfg)
        assert result.n_events_output == 2
        assert result.n_filtered == 1

    def test_filter_where_prec(self, tmp_path: Path) -> None:
        events = [
            _make_consolidated_event(event_id=i)
            for i in range(4)
        ]
        events[0]["where_prec"] = 1
        events[1]["where_prec"] = 4  # excluded
        events[2]["where_prec"] = 5
        events[3]["where_prec"] = 6  # excluded

        store = _write_consolidated(
            tmp_path / "store.parquet", events
        )
        cfg = ViewpointConfig(
            consolidated_path=store,
            output_path=tmp_path / "vp" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
            exclude_where_prec=(4, 6),
        )

        result = build_ucdp_v1(cfg)
        assert result.n_events_output == 2
        assert result.n_filtered == 2

    def test_production_parity_profile_has_filters(
        self, tmp_path: Path
    ) -> None:
        from datafactory_viewpoint.profiles import load_profile

        cfg = load_profile(
            "production_parity",
            tmp_path / "store.parquet",
        )
        assert cfg.min_priogrid_gid == 1
        assert cfg.max_type_of_violence == 3
        assert cfg.exclude_where_prec == (4, 6)


# ---- Filtering: Beige (boundary conditions) ----


class TestFilteringBeige:

    def test_priogrid_gid_zero_filtered(
        self, tmp_path: Path
    ) -> None:
        """gid=0 should be filtered when min_priogrid_gid=1."""
        from conftest import make_ucdp_event, write_test_parquet

        events = [
            make_ucdp_event(event_id=1, priogrid_gid=0),
            make_ucdp_event(event_id=2, priogrid_gid=1),
        ]
        store = write_test_parquet(
            tmp_path / "store.parquet", events
        )
        cfg = ViewpointConfig(
            consolidated_path=store,
            output_path=tmp_path / "vp" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
            min_priogrid_gid=1,
        )
        result = build_ucdp_v1(cfg)
        assert result.n_events_output == 1
        assert result.n_filtered == 1

    def test_type_of_violence_at_boundary(
        self, tmp_path: Path
    ) -> None:
        """tov=3 kept, tov=4 filtered when max=3."""
        from conftest import make_ucdp_event, write_test_parquet

        events = [
            make_ucdp_event(event_id=1, type_of_violence=3),
            make_ucdp_event(event_id=2, type_of_violence=4),
        ]
        store = write_test_parquet(
            tmp_path / "store.parquet", events
        )
        cfg = ViewpointConfig(
            consolidated_path=store,
            output_path=tmp_path / "vp" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
            max_type_of_violence=3,
        )
        result = build_ucdp_v1(cfg)
        assert result.n_events_output == 1
        assert result.n_filtered == 1

    def test_where_prec_at_boundary(
        self, tmp_path: Path
    ) -> None:
        """where_prec=3 kept, where_prec=4 filtered."""
        from conftest import make_ucdp_event, write_test_parquet

        events = [
            make_ucdp_event(event_id=1, where_prec=3),
            make_ucdp_event(event_id=2, where_prec=4),
        ]
        store = write_test_parquet(
            tmp_path / "store.parquet", events
        )
        cfg = ViewpointConfig(
            consolidated_path=store,
            output_path=tmp_path / "vp" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
            exclude_where_prec=(4, 6),
        )
        result = build_ucdp_v1(cfg)
        assert result.n_events_output == 1
        assert result.n_filtered == 1


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


# ---- Profiles ----


class TestProfilesGreen:

    def test_load_production_parity(self, tmp_path: Path) -> None:
        from datafactory_viewpoint.profiles import load_profile

        cfg = load_profile(
            "production_parity", tmp_path / "store.parquet"
        )
        assert isinstance(cfg, ViewpointConfig)
        assert cfg.survivorship_strategy == "dot9_wins"
        assert cfg.distribution_strategy == "ceil_split"
        assert cfg.version == "production_parity"

    def test_load_with_override(self, tmp_path: Path) -> None:
        from datafactory_viewpoint.profiles import load_profile

        cfg = load_profile(
            "production_parity",
            tmp_path / "store.parquet",
            distribution_strategy="even_split",
        )
        assert cfg.survivorship_strategy == "dot9_wins"
        assert cfg.distribution_strategy == "even_split"

    def test_list_profiles(self) -> None:
        from datafactory_viewpoint.profiles import list_profiles

        profiles = list_profiles()
        assert "production_parity" in profiles

    def test_freestyle_still_works(self, tmp_path: Path) -> None:
        """Config without profile — freestyle mode with
        registered strategies.
        """
        cfg = ViewpointConfig(
            consolidated_path=tmp_path / "store.parquet",
            survivorship_strategy="dot9_wins",
            distribution_strategy="ceil_split",
            version="experiment_42",
        )
        assert cfg.version == "experiment_42"


class TestProfilesRed:

    def test_unknown_profile_raises(self, tmp_path: Path) -> None:
        from datafactory_viewpoint.profiles import load_profile

        with pytest.raises(KeyError, match="Unknown viewpoint profile"):
            load_profile("nonexistent", tmp_path / "store.parquet")
