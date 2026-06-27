"""Tests for ACLED viewpoint builder — mock-based, no network."""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from datafactory_viewpoint.builders.acled_v1 import (
    AcledViewpointConfig,
    build_acled_v1,
)
from datafactory_viewpoint.viewpoint_result import ViewpointResult

# ---- Helpers ----


def _make_consolidated_store(
    path: Path,
    n: int = 10,
    event_types: list[str] | None = None,
) -> Path:
    """Create a synthetic ACLED consolidated store."""
    if event_types is None:
        event_types = ["Battles", "Protests", "Riots"]

    events = {
        "event_id_cnty": [f"SOM{i:04d}" for i in range(n)],
        "event_date": [
            f"2020-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}"
            for i in range(n)
        ],
        "event_type": [
            event_types[i % len(event_types)] for i in range(n)
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


# ---- Config Validation ----


class TestAcledViewpointConfigGreen:

    def test_defaults(self, tmp_path: Path) -> None:
        cfg = AcledViewpointConfig(
            consolidated_path=tmp_path / "store.parquet"
        )
        assert cfg.version == "acled_v1"
        assert cfg.event_type_filter is None


class TestAcledViewpointConfigBeige:

    def test_rejects_empty_version(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="version"):
            AcledViewpointConfig(
                consolidated_path=tmp_path / "store.parquet",
                version="",
            )


# ---- Build Flow ----


class TestBuildAcledV1Green:

    def test_full_flow(self, tmp_path: Path) -> None:
        """Build viewpoint from consolidated store."""
        store_path = tmp_path / "store" / "acled_store.parquet"
        _make_consolidated_store(store_path, n=15)

        config = AcledViewpointConfig(
            consolidated_path=store_path,
            output_path=tmp_path / "viewpoint" / "acled_v1.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )

        result = build_acled_v1(config)

        assert isinstance(result, ViewpointResult)
        assert result.n_events_input == 15
        assert result.n_events_output == 15
        assert result.n_filtered == 0
        assert result.n_summary_expanded == 0
        assert result.output_path.exists()

        output = pq.read_table(result.output_path)
        assert "date_month" in output.column_names
        assert "_source_type" not in output.column_names
        assert "_harvest_digest" not in output.column_names

    def test_date_month_assignment(self, tmp_path: Path) -> None:
        """Each event gets date_month from event_date[:7]."""
        store_path = tmp_path / "store" / "store.parquet"
        _make_consolidated_store(store_path, n=5)

        config = AcledViewpointConfig(
            consolidated_path=store_path,
            output_path=tmp_path / "vp" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )

        build_acled_v1(config)

        output = pq.read_table(config.output_path)
        months = output.column("date_month").to_pylist()
        dates = output.column("event_date").to_pylist()
        for m, d in zip(months, dates, strict=True):
            assert m == d[:7]

    def test_event_type_filter(self, tmp_path: Path) -> None:
        """Event type filter removes non-matching events."""
        store_path = tmp_path / "store" / "store.parquet"
        _make_consolidated_store(
            store_path,
            n=12,
            event_types=["Battles", "Protests", "Riots"],
        )

        config = AcledViewpointConfig(
            consolidated_path=store_path,
            output_path=tmp_path / "vp" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
            event_type_filter=("Battles",),
        )

        result = build_acled_v1(config)

        assert result.n_events_output == 4
        assert result.n_filtered == 8

        output = pq.read_table(config.output_path)
        types = set(output.column("event_type").to_pylist())
        assert types == {"Battles"}

    def test_provenance_recorded(self, tmp_path: Path) -> None:
        """Build writes a ledger entry."""
        store_path = tmp_path / "store" / "store.parquet"
        _make_consolidated_store(store_path, n=3)

        config = AcledViewpointConfig(
            consolidated_path=store_path,
            output_path=tmp_path / "vp" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )

        build_acled_v1(config)

        assert config.ledger_path.exists()
        entry = json.loads(
            config.ledger_path.read_text()
            .strip()
            .splitlines()[-1]
        )
        assert entry["dataset"] == "acled_viewpoint"
        assert entry["n_events_output"] == 3
        assert "output_digest" in entry

    def test_from_shortcuts_consolidated_path(
        self, tmp_path: Path,
    ) -> None:
        """Config.from_shortcuts() convenience API works."""
        store_path = tmp_path / "store" / "store.parquet"
        _make_consolidated_store(store_path, n=3)

        config = AcledViewpointConfig.from_shortcuts(
            consolidated_path=store_path,
        )
        result = build_acled_v1(config)
        assert result.n_events_output == 3


class TestBuildAcledV1Beige:

    def test_missing_store_raises(self, tmp_path: Path) -> None:
        config = AcledViewpointConfig(
            consolidated_path=tmp_path / "missing.parquet",
            output_path=tmp_path / "vp" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )
        with pytest.raises(
            FileNotFoundError, match="not found"
        ):
            build_acled_v1(config)

    def test_empty_store_raises(self, tmp_path: Path) -> None:
        store_path = tmp_path / "store" / "store.parquet"
        store_path.parent.mkdir(parents=True)
        empty = pa.table({
            "event_id_cnty": pa.array([], type=pa.string()),
            "event_date": pa.array([], type=pa.string()),
            "event_type": pa.array([], type=pa.string()),
            "latitude": pa.array([], type=pa.float64()),
            "longitude": pa.array([], type=pa.float64()),
            "fatalities": pa.array([], type=pa.int64()),
        })
        pq.write_table(empty, store_path)

        config = AcledViewpointConfig(
            consolidated_path=store_path,
            output_path=tmp_path / "vp" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )
        with pytest.raises(ValueError, match="empty"):
            build_acled_v1(config)

    def test_no_args_raises(self) -> None:
        with pytest.raises(TypeError):
            build_acled_v1()  # type: ignore[call-arg]


# ---- Red Team (Adversarial) ----


class TestBuildAcledV1Red:

    def test_malformed_event_date(self, tmp_path: Path) -> None:
        """Non-ISO event_date produces truncated date_month."""
        store_path = tmp_path / "store" / "store.parquet"
        _make_consolidated_store(store_path, n=3)

        output = pq.read_table(store_path)
        bad_dates = pa.array(
            ["2020/01/15", "bad", ""],
            type=pa.string(),
        )
        output = output.set_column(
            output.column_names.index("event_date"),
            "event_date",
            bad_dates,
        )
        pq.write_table(output, store_path)

        config = AcledViewpointConfig(
            consolidated_path=store_path,
            output_path=tmp_path / "vp" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )

        build_acled_v1(config)
        vp = pq.read_table(config.output_path)
        months = vp.column("date_month").to_pylist()
        assert months[0] == "2020/01"
        assert months[1] == "bad"[:7]

    def test_filter_eliminates_all_events(
        self, tmp_path: Path,
    ) -> None:
        """Filter matching zero events writes empty output."""
        store_path = tmp_path / "store" / "store.parquet"
        _make_consolidated_store(
            store_path, n=5, event_types=["Battles"],
        )

        config = AcledViewpointConfig(
            consolidated_path=store_path,
            output_path=tmp_path / "vp" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
            event_type_filter=("Nonexistent",),
        )

        result = build_acled_v1(config)
        assert result.n_events_output == 0
        assert result.n_filtered == 5
        assert result.output_path.exists()

    def test_missing_required_field_in_store(
        self, tmp_path: Path,
    ) -> None:
        """Consolidated store missing event_type raises."""
        store_path = tmp_path / "store" / "store.parquet"
        table = pa.table({
            "event_id_cnty": ["SOM0001"],
            "event_date": ["2020-01-15"],
            "latitude": [2.0],
            "longitude": [45.0],
            "fatalities": [0],
        })
        store_path.parent.mkdir(parents=True)
        pq.write_table(table, store_path)

        config = AcledViewpointConfig(
            consolidated_path=store_path,
            output_path=tmp_path / "vp" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
        )
        with pytest.raises(
            ValueError, match="missing required fields"
        ):
            build_acled_v1(config)

    def test_frozen_config_mutation(
        self, tmp_path: Path,
    ) -> None:
        """AcledViewpointConfig rejects mutation."""
        cfg = AcledViewpointConfig(
            consolidated_path=tmp_path / "store.parquet",
        )
        with pytest.raises(AttributeError):
            cfg.version = "new"  # type: ignore[misc]


# ---- ACLED Profiles ----


class TestAcledProfilesGreen:

    def test_load_acled_violence_only(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.profiles import (
            load_acled_profile,
        )

        cfg = load_acled_profile(
            "acled_violence_only",
            tmp_path / "store.parquet",
        )
        assert isinstance(cfg, AcledViewpointConfig)
        assert cfg.event_type_filter == (
            "Battles",
            "Explosions/Remote violence",
            "Violence against civilians",
        )
        assert cfg.version == "acled_violence_only"

    def test_load_acled_all_events(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.profiles import (
            load_acled_profile,
        )

        cfg = load_acled_profile(
            "acled_all_events",
            tmp_path / "store.parquet",
        )
        assert isinstance(cfg, AcledViewpointConfig)
        assert cfg.event_type_filter is None
        assert cfg.version == "acled_all_events"

    def test_load_with_override(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.profiles import (
            load_acled_profile,
        )

        cfg = load_acled_profile(
            "acled_violence_only",
            tmp_path / "store.parquet",
            event_type_filter=("Battles",),
        )
        assert cfg.event_type_filter == ("Battles",)

    def test_list_acled_profiles(self) -> None:
        from datafactory_viewpoint.profiles import (
            list_acled_profiles,
        )

        profiles = list_acled_profiles()
        assert "acled_violence_only" in profiles
        assert "acled_all_events" in profiles


class TestAcledProfilesRed:

    def test_unknown_acled_profile_raises(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.profiles import (
            load_acled_profile,
        )

        with pytest.raises(KeyError, match="Unknown ACLED"):
            load_acled_profile(
                "nonexistent", tmp_path / "store.parquet"
            )


# ---- Registration ----


class TestAcledBuilderRegistration:

    def test_registered(self) -> None:
        import datafactory_viewpoint.builders.acled_v1  # noqa: F401
        from datafactory_viewpoint.builders import list_builders

        assert "acled_v1" in list_builders()
