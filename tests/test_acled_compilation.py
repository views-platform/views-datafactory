"""Tests for ACLED compilation — events to PRIO-GRID features.

Uses a tiny 8-cell grid and synthetic ACLED events. Verifies
that the 8-feature ACLED compilation config (ADR-028) produces
correct per-type counts and fatality sums.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from datafactory_compilation.compilation_config import (
    CompilationConfig,
    FeatureSpec,
)
from datafactory_compilation.grid_compilation import compile_grid
from datafactory_priogrid.cell_generator import latlon_to_pgid
from datafactory_priogrid.grid_config import GridConfig
from datafactory_priogrid.temporal_config import TemporalConfig

TINY_GRID = GridConfig(resolution=90.0)
TINY_TEMPORAL = TemporalConfig(start_year=2024, end_year=2024)

ACLED_FEATURES = (
    FeatureSpec("acled_count", "count"),
    FeatureSpec(
        "acled_battles", "count",
        {"event_type": "Battles"},
    ),
    FeatureSpec(
        "acled_explosions", "count",
        {"event_type": "Explosions/Remote violence"},
    ),
    FeatureSpec(
        "acled_vac", "count",
        {"event_type": "Violence against civilians"},
    ),
    FeatureSpec(
        "acled_protests", "count",
        {"event_type": "Protests"},
    ),
    FeatureSpec(
        "acled_riots", "count",
        {"event_type": "Riots"},
    ),
    FeatureSpec(
        "acled_strategic", "count",
        {"event_type": "Strategic developments"},
    ),
    FeatureSpec(
        "acled_fatalities", "sum_field",
        value_field="fatalities",
    ),
)


def _make_acled_parquet(
    path: Path, events: list[dict],
) -> Path:
    """Write ACLED-shaped events to Parquet."""
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


def _make_acled_events() -> list[dict]:
    """Synthetic ACLED events at known locations."""
    return [
        {
            "event_id_cnty": "TST001",
            "event_date": "2024-01-15",
            "event_type": "Battles",
            "latitude": -45.0,
            "longitude": -90.0,
            "fatalities": 10,
        },
        {
            "event_id_cnty": "TST002",
            "event_date": "2024-01-20",
            "event_type": "Battles",
            "latitude": -45.0,
            "longitude": -90.0,
            "fatalities": 5,
        },
        {
            "event_id_cnty": "TST003",
            "event_date": "2024-01-10",
            "event_type": "Protests",
            "latitude": -45.0,
            "longitude": -90.0,
            "fatalities": 0,
        },
        {
            "event_id_cnty": "TST004",
            "event_date": "2024-03-10",
            "event_type": "Riots",
            "latitude": 45.0,
            "longitude": -90.0,
            "fatalities": 3,
        },
        {
            "event_id_cnty": "TST005",
            "event_date": "2024-03-12",
            "event_type": "Violence against civilians",
            "latitude": 45.0,
            "longitude": -90.0,
            "fatalities": 7,
        },
    ]


def _cell_indices(
    lat: float, lon: float,
) -> tuple[int, int]:
    """Return (row, col) for a lat/lon in the tiny grid."""
    pgid = int(latlon_to_pgid(lat, lon, TINY_GRID))
    ncol = TINY_GRID.ncol
    return (pgid - 1) // ncol, (pgid - 1) % ncol


def _acled_config(
    tmp_path: Path,
    source: Path,
) -> CompilationConfig:
    """Build ACLED compilation config for tests."""
    return CompilationConfig(
        source_path=source,
        grid_config=TINY_GRID,
        temporal_config=TINY_TEMPORAL,
        features=ACLED_FEATURES,
        output_dir=tmp_path / "output",
        ledger_path=tmp_path / "ledger.jsonl",
        date_field="event_date",
        lat_field="latitude",
        lon_field="longitude",
    )


class TestAcledCompilationGreen:
    """Green: correct behavior with valid ACLED data."""

    def test_produces_8_feature_channels(
        self, tmp_path: Path,
    ) -> None:
        events = _make_acled_events()
        src = _make_acled_parquet(
            tmp_path / "acled.parquet", events,
        )
        cfg = _acled_config(tmp_path, src)
        result = compile_grid(cfg)

        grid = np.load(result / "grid.npy")
        assert grid.shape == (12, 2, 4, 8)

    def test_feature_names_match_adr028(
        self, tmp_path: Path,
    ) -> None:
        events = _make_acled_events()
        src = _make_acled_parquet(
            tmp_path / "acled.parquet", events,
        )
        cfg = _acled_config(tmp_path, src)
        result = compile_grid(cfg)

        names = json.loads(
            (result / "feature_names.json").read_text()
        )
        assert names == [
            "acled_count",
            "acled_battles",
            "acled_explosions",
            "acled_vac",
            "acled_protests",
            "acled_riots",
            "acled_strategic",
            "acled_fatalities",
        ]

    def test_total_count_correct(
        self, tmp_path: Path,
    ) -> None:
        """acled_count sums all events per cell-month."""
        events = _make_acled_events()
        src = _make_acled_parquet(
            tmp_path / "acled.parquet", events,
        )
        cfg = _acled_config(tmp_path, src)
        compile_grid(cfg)
        grid = np.load(tmp_path / "output" / "grid.npy")

        row_sw, col_sw = _cell_indices(-45.0, -90.0)
        row_nw, col_nw = _cell_indices(45.0, -90.0)

        assert grid[0, row_sw, col_sw, 0] == 3.0
        assert grid[2, row_nw, col_nw, 0] == 2.0

    def test_per_type_counts_correct(
        self, tmp_path: Path,
    ) -> None:
        """Per-type features count only matching events."""
        events = _make_acled_events()
        src = _make_acled_parquet(
            tmp_path / "acled.parquet", events,
        )
        cfg = _acled_config(tmp_path, src)
        compile_grid(cfg)
        grid = np.load(tmp_path / "output" / "grid.npy")

        row_sw, col_sw = _cell_indices(-45.0, -90.0)
        row_nw, col_nw = _cell_indices(45.0, -90.0)

        # SW cell, Jan: 2 Battles + 1 Protest
        assert grid[0, row_sw, col_sw, 1] == 2.0  # battles
        assert grid[0, row_sw, col_sw, 4] == 1.0  # protests
        assert grid[0, row_sw, col_sw, 2] == 0.0  # explosions
        assert grid[0, row_sw, col_sw, 3] == 0.0  # vac
        assert grid[0, row_sw, col_sw, 5] == 0.0  # riots
        assert grid[0, row_sw, col_sw, 6] == 0.0  # strategic

        # NW cell, Mar: 1 Riot + 1 VaC
        assert grid[2, row_nw, col_nw, 5] == 1.0  # riots
        assert grid[2, row_nw, col_nw, 3] == 1.0  # vac

    def test_fatalities_sum_correct(
        self, tmp_path: Path,
    ) -> None:
        """acled_fatalities sums the fatalities field."""
        events = _make_acled_events()
        src = _make_acled_parquet(
            tmp_path / "acled.parquet", events,
        )
        cfg = _acled_config(tmp_path, src)
        compile_grid(cfg)
        grid = np.load(tmp_path / "output" / "grid.npy")

        row_sw, col_sw = _cell_indices(-45.0, -90.0)
        row_nw, col_nw = _cell_indices(45.0, -90.0)

        # SW cell, Jan: 10 + 5 + 0 = 15
        assert grid[0, row_sw, col_sw, 7] == 15.0
        # NW cell, Mar: 3 + 7 = 10
        assert grid[2, row_nw, col_nw, 7] == 10.0

    def test_type_counts_sum_to_total(
        self, tmp_path: Path,
    ) -> None:
        """Sum of per-type counts equals total count."""
        events = _make_acled_events()
        src = _make_acled_parquet(
            tmp_path / "acled.parquet", events,
        )
        cfg = _acled_config(tmp_path, src)
        compile_grid(cfg)
        grid = np.load(tmp_path / "output" / "grid.npy")

        total = grid[:, :, :, 0]
        type_sum = grid[:, :, :, 1:7].sum(axis=3)
        np.testing.assert_array_equal(total, type_sum)

    def test_provenance_recorded(
        self, tmp_path: Path,
    ) -> None:
        events = _make_acled_events()
        src = _make_acled_parquet(
            tmp_path / "acled.parquet", events,
        )
        cfg = _acled_config(tmp_path, src)
        result = compile_grid(cfg)

        prov = json.loads(
            (result / "provenance.json").read_text()
        )
        assert prov["grid_shape"] == [12, 2, 4, 8]
        assert len(prov["feature_names"]) == 8

        assert cfg.ledger_path.exists()


class TestAcledCompilationBeige:
    """Beige: boundary conditions."""

    def test_zero_fatalities_cell(
        self, tmp_path: Path,
    ) -> None:
        """Cell with only protests (0 fatalities)."""
        events = [
            {
                "event_id_cnty": "TST010",
                "event_date": "2024-06-01",
                "event_type": "Protests",
                "latitude": -45.0,
                "longitude": -90.0,
                "fatalities": 0,
            },
        ]
        src = _make_acled_parquet(
            tmp_path / "acled.parquet", events,
        )
        cfg = _acled_config(tmp_path, src)
        compile_grid(cfg)
        grid = np.load(tmp_path / "output" / "grid.npy")

        row, col = _cell_indices(-45.0, -90.0)
        assert grid[5, row, col, 0] == 1.0   # count
        assert grid[5, row, col, 4] == 1.0   # protests
        assert grid[5, row, col, 7] == 0.0   # fatalities

    def test_all_six_types_in_one_cell(
        self, tmp_path: Path,
    ) -> None:
        """One event per type in the same cell-month."""
        types = [
            "Battles",
            "Explosions/Remote violence",
            "Violence against civilians",
            "Protests",
            "Riots",
            "Strategic developments",
        ]
        events = [
            {
                "event_id_cnty": f"TST{i:03d}",
                "event_date": "2024-02-15",
                "event_type": t,
                "latitude": -45.0,
                "longitude": -90.0,
                "fatalities": i + 1,
            }
            for i, t in enumerate(types)
        ]
        src = _make_acled_parquet(
            tmp_path / "acled.parquet", events,
        )
        cfg = _acled_config(tmp_path, src)
        compile_grid(cfg)
        grid = np.load(tmp_path / "output" / "grid.npy")

        row, col = _cell_indices(-45.0, -90.0)
        assert grid[1, row, col, 0] == 6.0  # total
        for feat_idx in range(1, 7):
            assert grid[1, row, col, feat_idx] == 1.0
        # fatalities: 1+2+3+4+5+6 = 21
        assert grid[1, row, col, 7] == 21.0


class TestAcledCompilationRed:
    """Red: adversarial inputs."""

    def test_unknown_event_type_counted_in_total_only(
        self, tmp_path: Path,
    ) -> None:
        """An event_type not in the 6 known types counts in total but no type column."""
        events = [
            {
                "event_id_cnty": "TST020",
                "event_date": "2024-04-01",
                "event_type": "Unknown type",
                "latitude": -45.0,
                "longitude": -90.0,
                "fatalities": 1,
            },
        ]
        src = _make_acled_parquet(
            tmp_path / "acled.parquet", events,
        )
        cfg = _acled_config(tmp_path, src)
        compile_grid(cfg)
        grid = np.load(tmp_path / "output" / "grid.npy")

        row, col = _cell_indices(-45.0, -90.0)
        assert grid[3, row, col, 0] == 1.0  # total
        for feat_idx in range(1, 7):
            assert grid[3, row, col, feat_idx] == 0.0
        assert grid[3, row, col, 7] == 1.0  # fatalities

    def test_missing_fatalities_field_defaults_to_zero(
        self, tmp_path: Path,
    ) -> None:
        """Event without fatalities field sums as 0."""
        events = [
            {
                "event_id_cnty": "TST030",
                "event_date": "2024-05-01",
                "event_type": "Battles",
                "latitude": -45.0,
                "longitude": -90.0,
            },
        ]
        src = _make_acled_parquet(
            tmp_path / "acled.parquet", events,
        )
        cfg = _acled_config(tmp_path, src)
        compile_grid(cfg)
        grid = np.load(tmp_path / "output" / "grid.npy")

        row, col = _cell_indices(-45.0, -90.0)
        assert grid[4, row, col, 0] == 1.0  # counted
        assert grid[4, row, col, 7] == 0.0  # fatalities = 0
