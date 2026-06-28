"""Tests for spatial distribution (ADR-049).

Green / Beige / Red test taxonomy (ADR-005).
"""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from datafactory_viewpoint.spatial_distribution import (
    _distribute_value,
    get_spatial_distribution,
    passthrough,
    proportional,
)
from datafactory_viewpoint.spatial_weights import (
    SpatialWeightMap,
    build_spatial_weight_map,
)
from datafactory_viewpoint.viewpoint_config import ViewpointConfig

# ---- Helpers ----


def _write_gaul_parquet(
    path: Path,
    mapping: dict[int, int],
) -> Path:
    """Write a synthetic GAUL crosswalk parquet (gid, value)."""
    gids = list(mapping.keys())
    values = list(mapping.values())
    table = pa.table({
        "gid": pa.array(gids, type=pa.int32()),
        "value": pa.array(values, type=pa.int32()),
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)
    return path


def _make_event(
    *,
    event_id: int = 1,
    where_prec: int = 5,
    priogrid_gid: int = 100,
    best: int = 100,
    low: int = 50,
    high: int = 150,
) -> dict:
    """Minimal event dict for spatial distribution tests."""
    return {
        "id": event_id,
        "where_prec": where_prec,
        "priogrid_gid": priogrid_gid,
        "best": best,
        "low": low,
        "high": high,
        "date_start": "2023-06-15",
        "date_end": "2023-06-15",
        "date_prec": 1,
        "type_of_violence": 1,
        "_source_type": "annual",
        "_source_version": "25.1",
    }


def _simple_weight_map() -> SpatialWeightMap:
    """Weight map: admin-1 polygon 10 has 3 cells (50/30/20)."""
    return SpatialWeightMap(
        admin1_weights={
            10: {100: 0.5, 101: 0.3, 102: 0.2},
        },
        country_weights={
            1: {100: 0.5, 101: 0.3, 102: 0.2},
        },
        pgid_to_gaul1={100: 10, 101: 10, 102: 10},
        pgid_to_gaul0={100: 1, 101: 1, 102: 1},
        admin1_all_cells={10: [100, 101, 102]},
        country_all_cells={1: [100, 101, 102]},
    )


# ---- Green: _distribute_value ----


class TestDistributeValueGreen:

    def test_exact_split(self) -> None:
        """100 deaths across 50/30/20 = 50+30+20."""
        result = _distribute_value(
            100, {1: 0.5, 2: 0.3, 3: 0.2}
        )
        assert result == {1: 50, 2: 30, 3: 20}
        assert sum(result.values()) == 100

    def test_remainder_to_highest_weight(self) -> None:
        """7 across 50/30/20: floors 3+2+1=6, remainder 1 to pgid 1."""
        result = _distribute_value(
            7, {1: 0.5, 2: 0.3, 3: 0.2}
        )
        assert sum(result.values()) == 7
        assert result[1] == 4
        assert result[2] == 2
        assert result[3] == 1

    def test_conservation_prime(self) -> None:
        """Prime number (13) conserved exactly."""
        result = _distribute_value(
            13, {10: 0.5, 20: 0.3, 30: 0.2}
        )
        assert sum(result.values()) == 13

    def test_zero_value(self) -> None:
        """Zero deaths distributed as all zeros."""
        result = _distribute_value(
            0, {1: 0.5, 2: 0.3, 3: 0.2}
        )
        assert result == {1: 0, 2: 0, 3: 0}

    def test_one_death_one_cell(self) -> None:
        """Single death goes to the single cell."""
        result = _distribute_value(1, {5: 1.0})
        assert result == {5: 1}

    def test_tie_break_lowest_pgid(self) -> None:
        """Equal weights: remainder goes to lowest pgid."""
        result = _distribute_value(
            1, {200: 0.5, 100: 0.5}
        )
        assert sum(result.values()) == 1
        assert result[100] == 1
        assert result[200] == 0

    def test_empty_weights(self) -> None:
        """Empty weights returns empty dict."""
        assert _distribute_value(10, {}) == {}


# ---- Green: proportional strategy ----


class TestProportionalGreen:

    def test_well_located_passthrough(self) -> None:
        """where_prec <= 3 passes through unchanged."""
        event = _make_event(where_prec=2, best=10)
        result = proportional(event, _simple_weight_map())
        assert result == [event]

    def test_where_prec_4_uses_admin1(self) -> None:
        """where_prec=4 distributes across admin-1 polygon."""
        event = _make_event(
            where_prec=4, priogrid_gid=100, best=100,
        )
        wm = _simple_weight_map()
        result = proportional(event, wm)
        assert len(result) == 3
        total_best = sum(r["best"] for r in result)
        assert total_best == 100
        pgids = [r["priogrid_gid"] for r in result]
        assert sorted(pgids) == [100, 101, 102]

    def test_where_prec_5_uses_admin1(self) -> None:
        """where_prec=5 also uses admin-1."""
        event = _make_event(
            where_prec=5, priogrid_gid=100, best=10,
        )
        result = proportional(event, _simple_weight_map())
        assert len(result) == 3
        assert sum(r["best"] for r in result) == 10

    def test_where_prec_6_uses_country(self) -> None:
        """where_prec=6 uses country polygon."""
        event = _make_event(
            where_prec=6, priogrid_gid=100, best=100,
        )
        result = proportional(event, _simple_weight_map())
        assert len(result) == 3
        assert sum(r["best"] for r in result) == 100

    def test_where_prec_7_uses_country(self) -> None:
        """where_prec=7 (international) also uses country."""
        event = _make_event(
            where_prec=7, priogrid_gid=100, best=50,
        )
        result = proportional(event, _simple_weight_map())
        assert len(result) == 3
        assert sum(r["best"] for r in result) == 50

    def test_conservation_all_fields(self) -> None:
        """best, low, high all conserved independently."""
        event = _make_event(
            where_prec=4, best=100, low=50, high=150,
        )
        result = proportional(event, _simple_weight_map())
        assert sum(r["best"] for r in result) == 100
        assert sum(r["low"] for r in result) == 50
        assert sum(r["high"] for r in result) == 150

    def test_provenance_annotations(self) -> None:
        """Distributed rows carry spatial provenance."""
        event = _make_event(where_prec=5, priogrid_gid=100)
        result = proportional(event, _simple_weight_map())
        for row in result:
            assert row["_spatial_distributed"] is True
            assert row["_spatial_source_pgid"] == 100
            assert row["_spatial_polygon_code"] == 10
            assert row["_spatial_n_cells"] == 3

    def test_sorted_output_by_pgid(self) -> None:
        """Output rows are sorted by pgid."""
        event = _make_event(where_prec=4)
        result = proportional(event, _simple_weight_map())
        pgids = [r["priogrid_gid"] for r in result]
        assert pgids == sorted(pgids)

    def test_original_fields_preserved(self) -> None:
        """Non-distributed fields carry through."""
        event = _make_event(where_prec=4)
        result = proportional(event, _simple_weight_map())
        for row in result:
            assert row["date_start"] == "2023-06-15"
            assert row["type_of_violence"] == 1
            assert row["id"] == 1


# ---- Green: passthrough strategy ----


class TestPassthroughGreen:

    def test_passthrough_returns_event_unchanged(self) -> None:
        event = _make_event(where_prec=5, best=100)
        result = passthrough(event, _simple_weight_map())
        assert result == [event]

    def test_passthrough_ignores_weight_map(self) -> None:
        event = _make_event(where_prec=6)
        result = passthrough(event, SpatialWeightMap())
        assert result == [event]


# ---- Green: get_spatial_distribution registry ----


class TestRegistryGreen:

    def test_lookup_proportional(self) -> None:
        fn = get_spatial_distribution("proportional")
        assert fn is proportional

    def test_lookup_passthrough(self) -> None:
        fn = get_spatial_distribution("passthrough")
        assert fn is passthrough


# ---- Green: build_spatial_weight_map ----


class TestWeightMapGreen:

    def test_weights_sum_to_one(self, tmp_path: Path) -> None:
        """Weights within each polygon sum to 1.0."""
        gaul1 = _write_gaul_parquet(
            tmp_path / "gaul1.parquet",
            {10: 100, 11: 100, 12: 200},
        )
        gaul0 = _write_gaul_parquet(
            tmp_path / "gaul0.parquet",
            {10: 1, 11: 1, 12: 1},
        )
        table = pa.table({
            "where_prec": [1, 1, 1],
            "priogrid_gid": [10, 11, 12],
            "best": [60, 30, 10],
        })
        wm = build_spatial_weight_map(table, gaul1, gaul0)
        for weights in wm.admin1_weights.values():
            assert abs(sum(weights.values()) - 1.0) < 1e-9
        for weights in wm.country_weights.values():
            assert abs(sum(weights.values()) - 1.0) < 1e-9

    def test_well_located_only(self, tmp_path: Path) -> None:
        """Only where_prec <= 3 events contribute to weights."""
        gaul1 = _write_gaul_parquet(
            tmp_path / "gaul1.parquet", {10: 100},
        )
        gaul0 = _write_gaul_parquet(
            tmp_path / "gaul0.parquet", {10: 1},
        )
        table = pa.table({
            "where_prec": [1, 5],
            "priogrid_gid": [10, 10],
            "best": [50, 1000],
        })
        wm = build_spatial_weight_map(table, gaul1, gaul0)
        assert wm.admin1_weights[100][10] == 1.0

    def test_gaul_minus1_excluded(self, tmp_path: Path) -> None:
        """Cells with gaul_code=-1 excluded from crosswalk."""
        gaul1 = _write_gaul_parquet(
            tmp_path / "gaul1.parquet", {10: -1, 11: 100},
        )
        gaul0 = _write_gaul_parquet(
            tmp_path / "gaul0.parquet", {10: -1, 11: 1},
        )
        table = pa.table({
            "where_prec": [1, 1],
            "priogrid_gid": [10, 11],
            "best": [50, 50],
        })
        wm = build_spatial_weight_map(table, gaul1, gaul0)
        assert 10 not in wm.pgid_to_gaul1
        assert 11 in wm.pgid_to_gaul1

    def test_all_cells_populated(self, tmp_path: Path) -> None:
        """admin1_all_cells and country_all_cells populated."""
        gaul1 = _write_gaul_parquet(
            tmp_path / "gaul1.parquet",
            {10: 100, 11: 100, 12: 200},
        )
        gaul0 = _write_gaul_parquet(
            tmp_path / "gaul0.parquet",
            {10: 1, 11: 1, 12: 2},
        )
        table = pa.table({
            "where_prec": [1],
            "priogrid_gid": [10],
            "best": [10],
        })
        wm = build_spatial_weight_map(table, gaul1, gaul0)
        assert sorted(wm.admin1_all_cells[100]) == [10, 11]
        assert wm.admin1_all_cells[200] == [12]
        assert sorted(wm.country_all_cells[1]) == [10, 11]


# ---- Green: ViewpointConfig spatial validation ----


class TestConfigGreen:

    def test_default_spatial_strategy(
        self, tmp_path: Path
    ) -> None:
        """Default config has proportional spatial strategy."""
        cfg = ViewpointConfig(
            consolidated_path=tmp_path / "store.parquet",
        )
        assert cfg.spatial_distribution_strategy == "proportional"

    def test_passthrough_spatial_strategy(
        self, tmp_path: Path
    ) -> None:
        cfg = ViewpointConfig(
            consolidated_path=tmp_path / "store.parquet",
            spatial_distribution_strategy="passthrough",
        )
        assert cfg.spatial_distribution_strategy == "passthrough"


# ---- Green: builder integration ----


class TestBuilderIntegrationGreen:

    def test_passthrough_no_spatial_expansion(
        self, tmp_path: Path
    ) -> None:
        """Passthrough strategy produces zero spatial expansion."""
        from conftest import make_ucdp_event, write_test_parquet

        from datafactory_viewpoint.builders.ucdp_v1 import (
            build_ucdp_v1,
        )

        events = [
            make_ucdp_event(
                event_id=1, where_prec=5, priogrid_gid=100,
            ),
        ]
        store = write_test_parquet(
            tmp_path / "store.parquet", events,
        )
        cfg = ViewpointConfig(
            consolidated_path=store,
            output_path=tmp_path / "vp" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
            spatial_distribution_strategy="passthrough",
        )
        result = build_ucdp_v1(cfg)
        assert result.n_spatially_distributed == 0
        assert result.n_events_output == 1

    def test_proportional_with_gaul_crosswalks(
        self, tmp_path: Path
    ) -> None:
        """End-to-end: where_prec=5 event distributed with GAUL."""
        from conftest import make_ucdp_event, write_test_parquet

        from datafactory_viewpoint.builders.ucdp_v1 import (
            build_ucdp_v1,
        )

        events = [
            make_ucdp_event(
                event_id=1, where_prec=1, priogrid_gid=10,
                best=60,
            ),
            make_ucdp_event(
                event_id=2, where_prec=1, priogrid_gid=11,
                best=40,
            ),
            make_ucdp_event(
                event_id=3, where_prec=5, priogrid_gid=10,
                best=100,
            ),
        ]
        store = write_test_parquet(
            tmp_path / "store.parquet", events,
        )
        gaul1 = _write_gaul_parquet(
            tmp_path / "gaul1.parquet",
            {10: 100, 11: 100},
        )
        gaul0 = _write_gaul_parquet(
            tmp_path / "gaul0.parquet",
            {10: 1, 11: 1},
        )
        cfg = ViewpointConfig(
            consolidated_path=store,
            output_path=tmp_path / "vp" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
            spatial_distribution_strategy="proportional",
            gaul1_crosswalk_path=gaul1,
            gaul0_crosswalk_path=gaul0,
        )
        result = build_ucdp_v1(cfg)
        assert result.n_spatially_distributed == 1
        output = pq.read_table(result.output_path)
        bests = output.column("best").to_pylist()
        assert sum(bests) == 60 + 40 + 100

    def test_spatial_distributed_bypasses_where_prec_filter(
        self, tmp_path: Path
    ) -> None:
        """Spatially distributed events bypass exclude_where_prec."""
        from conftest import make_ucdp_event, write_test_parquet

        from datafactory_viewpoint.builders.ucdp_v1 import (
            build_ucdp_v1,
        )

        events = [
            make_ucdp_event(
                event_id=1, where_prec=1, priogrid_gid=10,
                best=50,
            ),
            make_ucdp_event(
                event_id=2, where_prec=5, priogrid_gid=10,
                best=30,
            ),
        ]
        store = write_test_parquet(
            tmp_path / "store.parquet", events,
        )
        gaul1 = _write_gaul_parquet(
            tmp_path / "gaul1.parquet", {10: 100},
        )
        gaul0 = _write_gaul_parquet(
            tmp_path / "gaul0.parquet", {10: 1},
        )
        cfg = ViewpointConfig(
            consolidated_path=store,
            output_path=tmp_path / "vp" / "out.parquet",
            ledger_path=tmp_path / "prov" / "ledger.jsonl",
            spatial_distribution_strategy="proportional",
            gaul1_crosswalk_path=gaul1,
            gaul0_crosswalk_path=gaul0,
            exclude_where_prec=(5,),
        )
        result = build_ucdp_v1(cfg)
        assert result.n_events_output == 2
        output = pq.read_table(result.output_path)
        total = sum(output.column("best").to_pylist())
        assert total == 50 + 30


# ---- Green: temporal + spatial composition ----


class TestCompositionGreen:

    def test_temporal_then_spatial(self) -> None:
        """Temporal first, then spatial; each conserves."""
        from datafactory_viewpoint.temporal_distribution import (
            get_distribution,
        )

        event = _make_event(
            where_prec=5, best=12, low=6, high=18,
        )
        event["date_prec"] = 5
        event["date_start"] = "2023-03-01"
        event["date_end"] = "2023-05-31"

        temporal_fn = get_distribution("ceil_split")
        temporal_rows = temporal_fn(event)
        assert len(temporal_rows) == 3
        assert sum(r["best"] for r in temporal_rows) == 12

        wm = _simple_weight_map()
        spatial_rows = []
        for row in temporal_rows:
            spatial_rows.extend(proportional(row, wm))

        assert len(spatial_rows) == 9
        assert sum(r["best"] for r in spatial_rows) == 12
        assert sum(r["low"] for r in spatial_rows) == 6
        assert sum(r["high"] for r in spatial_rows) == 18


# ---- Beige: edge cases ----


class TestProportionalBeige:

    def test_zero_fatality_polygon_uniform(self) -> None:
        """Polygon with no well-located fatalities -> uniform."""
        wm = SpatialWeightMap(
            admin1_weights={},
            country_weights={},
            pgid_to_gaul1={100: 10, 101: 10, 102: 10},
            pgid_to_gaul0={100: 1, 101: 1, 102: 1},
            admin1_all_cells={10: [100, 101, 102]},
            country_all_cells={1: [100, 101, 102]},
        )
        event = _make_event(
            where_prec=4, priogrid_gid=100, best=9,
        )
        result = proportional(event, wm)
        assert len(result) == 3
        assert sum(r["best"] for r in result) == 9

    def test_single_cell_polygon(self) -> None:
        """One-cell polygon: all deaths to that cell."""
        wm = SpatialWeightMap(
            admin1_weights={10: {100: 1.0}},
            country_weights={1: {100: 1.0}},
            pgid_to_gaul1={100: 10},
            pgid_to_gaul0={100: 1},
            admin1_all_cells={10: [100]},
            country_all_cells={1: [100]},
        )
        event = _make_event(
            where_prec=5, priogrid_gid=100, best=77,
        )
        result = proportional(event, wm)
        assert len(result) == 1
        assert result[0]["best"] == 77
        assert result[0]["priogrid_gid"] == 100

    def test_where_prec_3_boundary_passthrough(self) -> None:
        """where_prec=3 (boundary) passes through unchanged."""
        event = _make_event(where_prec=3, best=100)
        result = proportional(event, _simple_weight_map())
        assert result == [event]

    def test_centroid_in_water_passthrough(self) -> None:
        """Centroid cell with no GAUL code passes through."""
        wm = SpatialWeightMap(
            admin1_weights={},
            country_weights={},
            pgid_to_gaul1={},
            pgid_to_gaul0={},
            admin1_all_cells={},
            country_all_cells={},
        )
        event = _make_event(
            where_prec=5, priogrid_gid=999, best=10,
        )
        result = proportional(event, wm)
        assert result == [event]

    def test_country_centroid_in_water_passthrough(self) -> None:
        """Country-level (where_prec=6) centroid in water passes through."""
        wm = SpatialWeightMap(
            admin1_weights={},
            country_weights={},
            pgid_to_gaul1={},
            pgid_to_gaul0={},
            admin1_all_cells={},
            country_all_cells={},
        )
        event = _make_event(
            where_prec=6, priogrid_gid=999, best=10,
        )
        result = proportional(event, wm)
        assert result == [event]

    def test_best_zero_distributed_as_zeros(self) -> None:
        """best=0 distributes as all-zero cells."""
        event = _make_event(
            where_prec=4, priogrid_gid=100,
            best=0, low=0, high=0,
        )
        result = proportional(event, _simple_weight_map())
        assert len(result) == 3
        assert all(r["best"] == 0 for r in result)

    def test_no_priogrid_gid_passthrough(self) -> None:
        """Event with no priogrid_gid passes through."""
        event = _make_event(where_prec=5, best=10)
        del event["priogrid_gid"]
        result = proportional(event, _simple_weight_map())
        assert result == [event]

    def test_priogrid_gid_zero_passthrough(self) -> None:
        """Event with priogrid_gid=0 passes through."""
        event = _make_event(
            where_prec=5, priogrid_gid=0, best=10,
        )
        result = proportional(event, _simple_weight_map())
        assert result == [event]


class TestWeightMapBeige:

    def test_no_well_located_events(
        self, tmp_path: Path
    ) -> None:
        """All events imprecise -> empty weights, all_cells populated."""
        gaul1 = _write_gaul_parquet(
            tmp_path / "gaul1.parquet", {10: 100},
        )
        gaul0 = _write_gaul_parquet(
            tmp_path / "gaul0.parquet", {10: 1},
        )
        table = pa.table({
            "where_prec": [5, 6],
            "priogrid_gid": [10, 10],
            "best": [50, 100],
        })
        wm = build_spatial_weight_map(table, gaul1, gaul0)
        assert len(wm.admin1_weights) == 0
        assert 100 in wm.admin1_all_cells

    def test_multiple_events_same_cell(
        self, tmp_path: Path
    ) -> None:
        """Multiple well-located events in same cell aggregate."""
        gaul1 = _write_gaul_parquet(
            tmp_path / "gaul1.parquet",
            {10: 100, 11: 100},
        )
        gaul0 = _write_gaul_parquet(
            tmp_path / "gaul0.parquet",
            {10: 1, 11: 1},
        )
        table = pa.table({
            "where_prec": [1, 1, 1],
            "priogrid_gid": [10, 10, 11],
            "best": [30, 30, 40],
        })
        wm = build_spatial_weight_map(table, gaul1, gaul0)
        assert abs(wm.admin1_weights[100][10] - 0.6) < 1e-9
        assert abs(wm.admin1_weights[100][11] - 0.4) < 1e-9


# ---- Red: error paths ----


class TestRegistryRed:

    def test_unknown_strategy_raises(self) -> None:
        with pytest.raises(KeyError):
            get_spatial_distribution("nonexistent")


class TestWeightMapRed:

    def test_missing_gaul1_raises(self, tmp_path: Path) -> None:
        gaul0 = _write_gaul_parquet(
            tmp_path / "gaul0.parquet", {10: 1},
        )
        table = pa.table({
            "where_prec": [1],
            "priogrid_gid": [10],
            "best": [10],
        })
        with pytest.raises(FileNotFoundError):
            build_spatial_weight_map(
                table,
                tmp_path / "missing.parquet",
                gaul0,
            )

    def test_missing_gaul0_raises(self, tmp_path: Path) -> None:
        gaul1 = _write_gaul_parquet(
            tmp_path / "gaul1.parquet", {10: 100},
        )
        table = pa.table({
            "where_prec": [1],
            "priogrid_gid": [10],
            "best": [10],
        })
        with pytest.raises(FileNotFoundError):
            build_spatial_weight_map(
                table,
                gaul1,
                tmp_path / "missing.parquet",
            )


class TestConfigRed:

    def test_invalid_spatial_strategy_raises(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(ValueError, match="spatial"):
            ViewpointConfig(
                consolidated_path=tmp_path / "store.parquet",
                spatial_distribution_strategy="bogus",
            )


# ---- Green: production_parity profile ----


class TestProfileGreen:

    def test_production_parity_uses_passthrough(self) -> None:
        from datafactory_viewpoint.profiles import PROFILES

        overrides = PROFILES["production_parity"]
        assert (
            overrides["spatial_distribution_strategy"]
            == "passthrough"
        )


# ---- Red: ViewpointResult frozen ----


class TestViewpointResultRed:

    def test_frozen_prevents_mutation(self) -> None:
        """ViewpointResult rejects field mutation."""
        from dataclasses import FrozenInstanceError

        from datafactory_viewpoint.viewpoint_result import (
            ViewpointResult,
        )

        result = ViewpointResult(
            output_path=Path("/tmp/out.parquet"),
            n_events_input=100,
            n_events_output=90,
            n_summary_expanded=5,
            n_spatially_distributed=10,
            n_filtered=5,
            output_digest="abc123",
            version="v1",
        )
        with pytest.raises(FrozenInstanceError):
            result.version = "v2"  # type: ignore[misc]
