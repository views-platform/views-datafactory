"""Tests for SHDI viewpoint builder — GDL region-year to grid-monthly.

Green: happy path (crosswalk, expansion, output format, month_id).
Beige: boundary conditions (unmapped regions, year filtering).
Red: failure handling (missing files, empty config).

Ref: ADR-036 (SHDI source selection), ADR-040 (intensive quantities).
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_VARIABLES = ("shdi", "healthindex")


def _write_crosswalk(path: Path) -> None:
    """Write a minimal GDL gdl_to_pgid.parquet crosswalk."""
    table = pa.table({
        "gid": pa.array(
            [100, 101, 200, 201, 202], type=pa.int32(),
        ),
        "gdl_code": pa.array(
            ["NORr101", "NORr101", "SWEr201", "SWEr201", "SWEr202"],
            type=pa.string(),
        ),
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


def _write_source(
    path: Path,
    *,
    regions: list[str] | None = None,
    years: list[int] | None = None,
    variables: tuple[str, ...] = SAMPLE_VARIABLES,
) -> None:
    """Write a minimal SHDI harvest Parquet."""
    if regions is None:
        regions = ["NORr101", "SWEr201"]
    if years is None:
        years = [2020, 2021]

    rows_gdl: list[str] = []
    rows_year: list[int] = []
    rows_vals: dict[str, list[float]] = {v: [] for v in variables}

    val = 0.5
    for gdl_code in regions:
        for year in years:
            rows_gdl.append(gdl_code)
            rows_year.append(year)
            for v in variables:
                rows_vals[v].append(round(val, 4))
                val += 0.01

    columns: dict[str, pa.Array] = {
        "GDLCODE": pa.array(rows_gdl, type=pa.string()),
        "Year": pa.array(rows_year, type=pa.int64()),
    }
    for v in variables:
        columns[v] = pa.array(rows_vals[v], type=pa.float64())

    table = pa.table(columns)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


# ===================================================================
# GREEN — Config
# ===================================================================


class TestShdiViewpointConfigGreen:
    """Config defaults and immutability."""

    def test_defaults(self) -> None:
        from datafactory_viewpoint.builders.shdi_v1 import (
            ShdiViewpointConfig,
        )

        cfg = ShdiViewpointConfig()
        assert len(cfg.variables) == 4
        assert cfg.start_year == 1990
        assert cfg.end_year == 2023
        assert cfg.version == "shdi_v1"

    def test_frozen(self) -> None:
        from datafactory_viewpoint.builders.shdi_v1 import (
            ShdiViewpointConfig,
        )

        cfg = ShdiViewpointConfig()
        with pytest.raises(AttributeError):
            cfg.version = "v2"  # type: ignore[misc]


# ===================================================================
# GREEN — Build
# ===================================================================


class TestBuildShdiV1Green:
    """Happy-path viewpoint build."""

    def test_basic_expansion(self, tmp_path: Path) -> None:
        from datafactory_viewpoint.builders.shdi_v1 import (
            ShdiViewpointConfig,
            build_shdi_v1,
        )

        source = tmp_path / "source.parquet"
        crosswalk = tmp_path / "gdl_to_pgid.parquet"
        output = tmp_path / "shdi_v1.parquet"

        _write_source(source, variables=SAMPLE_VARIABLES)
        _write_crosswalk(crosswalk)

        config = ShdiViewpointConfig(
            source_path=source,
            crosswalk_path=crosswalk,
            output_path=output,
            ledger_path=tmp_path / "ledger.jsonl",
            variables=SAMPLE_VARIABLES,
            start_year=2020,
            end_year=2021,
        )

        result = build_shdi_v1(config)

        assert result.output_path == output
        assert output.exists()
        assert result.n_events_input == 4
        # NORr101 has 2 pgids, SWEr201 has 2 pgids
        # → (2+2) × 2 years × 12 months = 96
        assert result.n_events_output == 96

    def test_output_columns(self, tmp_path: Path) -> None:
        from datafactory_viewpoint.builders.shdi_v1 import (
            ShdiViewpointConfig,
            build_shdi_v1,
        )

        source = tmp_path / "source.parquet"
        crosswalk = tmp_path / "gdl_to_pgid.parquet"
        output = tmp_path / "shdi_v1.parquet"

        _write_source(source, variables=SAMPLE_VARIABLES)
        _write_crosswalk(crosswalk)

        config = ShdiViewpointConfig(
            source_path=source,
            crosswalk_path=crosswalk,
            output_path=output,
            ledger_path=tmp_path / "ledger.jsonl",
            variables=SAMPLE_VARIABLES,
            start_year=2020,
            end_year=2021,
        )

        build_shdi_v1(config)

        table = pq.read_table(output)
        col_names = set(table.column_names)
        assert "pgid" in col_names
        assert "month_id" in col_names
        for var in SAMPLE_VARIABLES:
            assert var in col_names

    def test_values_constant_within_year(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.shdi_v1 import (
            ShdiViewpointConfig,
            build_shdi_v1,
        )

        source = tmp_path / "source.parquet"
        crosswalk = tmp_path / "gdl_to_pgid.parquet"
        output = tmp_path / "shdi_v1.parquet"

        _write_source(
            source,
            regions=["NORr101"],
            years=[2020],
            variables=SAMPLE_VARIABLES,
        )
        _write_crosswalk(crosswalk)

        config = ShdiViewpointConfig(
            source_path=source,
            crosswalk_path=crosswalk,
            output_path=output,
            ledger_path=tmp_path / "ledger.jsonl",
            variables=SAMPLE_VARIABLES,
            start_year=2020,
            end_year=2020,
        )

        build_shdi_v1(config)

        table = pq.read_table(output)
        # NORr101 has 2 pgids × 12 months = 24 rows
        assert table.num_rows == 24

        pgids = table.column("pgid").to_pylist()
        vals = table.column("shdi").to_pylist()

        pgid100_vals = [
            v for p, v in zip(pgids, vals, strict=True)
            if p == 100
        ]
        assert len(pgid100_vals) == 12
        assert len(set(pgid100_vals)) == 1

    def test_month_id_calculation(self, tmp_path: Path) -> None:
        from datafactory_viewpoint.builders.shdi_v1 import (
            ShdiViewpointConfig,
            build_shdi_v1,
        )

        source = tmp_path / "source.parquet"
        crosswalk = tmp_path / "gdl_to_pgid.parquet"
        output = tmp_path / "shdi_v1.parquet"

        # Single region with 1 pgid for easy verification
        cw = pa.table({
            "gid": pa.array([1], type=pa.int32()),
            "gdl_code": pa.array(["TST"], type=pa.string()),
        })
        pq.write_table(cw, crosswalk)

        _write_source(
            source,
            regions=["TST"],
            years=[1990],
            variables=SAMPLE_VARIABLES,
        )

        config = ShdiViewpointConfig(
            source_path=source,
            crosswalk_path=crosswalk,
            output_path=output,
            ledger_path=tmp_path / "ledger.jsonl",
            variables=SAMPLE_VARIABLES,
            start_year=1990,
            end_year=1990,
        )

        build_shdi_v1(config)

        result_table = pq.read_table(output)
        month_ids = sorted(
            result_table.column("month_id").to_pylist()
        )
        # 1990: base_mid = (1990-1980)*12 = 120, months 121..132
        assert month_ids == list(range(121, 133))

    def test_provenance_ledger_written(
        self, tmp_path: Path,
    ) -> None:
        import json

        from datafactory_viewpoint.builders.shdi_v1 import (
            ShdiViewpointConfig,
            build_shdi_v1,
        )

        source = tmp_path / "source.parquet"
        crosswalk = tmp_path / "gdl_to_pgid.parquet"
        ledger = tmp_path / "ledger.jsonl"

        _write_source(source, variables=SAMPLE_VARIABLES)
        _write_crosswalk(crosswalk)

        config = ShdiViewpointConfig(
            source_path=source,
            crosswalk_path=crosswalk,
            output_path=tmp_path / "out.parquet",
            ledger_path=ledger,
            variables=SAMPLE_VARIABLES,
            start_year=2020,
            end_year=2021,
        )

        build_shdi_v1(config)

        assert ledger.exists()
        entries = [
            json.loads(line)
            for line in ledger.read_text().strip().split("\n")
        ]
        assert entries[-1]["outcome"] == "success"
        assert entries[-1]["dataset"] == "shdi_viewpoint"
        assert entries[-1]["n_variables"] == 2

    def test_twelve_months_per_year_per_pgid(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.shdi_v1 import (
            ShdiViewpointConfig,
            build_shdi_v1,
        )

        source = tmp_path / "source.parquet"
        crosswalk = tmp_path / "gdl_to_pgid.parquet"
        output = tmp_path / "shdi_v1.parquet"

        _write_source(
            source,
            regions=["NORr101"],
            years=[2020],
            variables=SAMPLE_VARIABLES,
        )
        _write_crosswalk(crosswalk)

        config = ShdiViewpointConfig(
            source_path=source,
            crosswalk_path=crosswalk,
            output_path=output,
            ledger_path=tmp_path / "ledger.jsonl",
            variables=SAMPLE_VARIABLES,
            start_year=2020,
            end_year=2020,
        )

        build_shdi_v1(config)

        table = pq.read_table(output)
        pgids = table.column("pgid").to_pylist()

        pgid_counts = Counter(pgids)
        for pgid, count in pgid_counts.items():
            assert count == 12, (
                f"pgid {pgid} has {count} rows, expected 12"
            )

    def test_no_duplicate_pgid_month_pairs(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.shdi_v1 import (
            ShdiViewpointConfig,
            build_shdi_v1,
        )

        source = tmp_path / "source.parquet"
        crosswalk = tmp_path / "gdl_to_pgid.parquet"
        output = tmp_path / "shdi_v1.parquet"

        _write_source(source, variables=SAMPLE_VARIABLES)
        _write_crosswalk(crosswalk)

        config = ShdiViewpointConfig(
            source_path=source,
            crosswalk_path=crosswalk,
            output_path=output,
            ledger_path=tmp_path / "ledger.jsonl",
            variables=SAMPLE_VARIABLES,
            start_year=2020,
            end_year=2021,
        )

        build_shdi_v1(config)

        table = pq.read_table(output)
        pgids = table.column("pgid").to_pylist()
        month_ids = table.column("month_id").to_pylist()

        pairs = list(zip(pgids, month_ids, strict=True))
        assert len(pairs) == len(set(pairs))

    def test_value_range_zero_to_one(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.shdi_v1 import (
            ShdiViewpointConfig,
            build_shdi_v1,
        )

        source = tmp_path / "source.parquet"
        crosswalk = tmp_path / "gdl_to_pgid.parquet"
        output = tmp_path / "shdi_v1.parquet"

        _write_source(source, variables=SAMPLE_VARIABLES)
        _write_crosswalk(crosswalk)

        config = ShdiViewpointConfig(
            source_path=source,
            crosswalk_path=crosswalk,
            output_path=output,
            ledger_path=tmp_path / "ledger.jsonl",
            variables=SAMPLE_VARIABLES,
            start_year=2020,
            end_year=2021,
        )

        build_shdi_v1(config)

        table = pq.read_table(output)
        for var in SAMPLE_VARIABLES:
            values = table.column(var).to_pylist()
            for v in values:
                assert 0.0 <= v <= 1.0, (
                    f"{var} value {v} outside [0, 1]"
                )


# ===================================================================
# BEIGE — Boundary conditions
# ===================================================================


class TestBuildShdiV1Beige:
    """Boundary conditions and warnings."""

    def test_unmapped_region_warns_not_crashes(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.shdi_v1 import (
            ShdiViewpointConfig,
            build_shdi_v1,
        )

        source = tmp_path / "source.parquet"
        crosswalk = tmp_path / "gdl_to_pgid.parquet"
        output = tmp_path / "shdi_v1.parquet"

        _write_source(
            source,
            regions=["NORr101", "XXXr999"],
            years=[2020],
            variables=SAMPLE_VARIABLES,
        )
        _write_crosswalk(crosswalk)

        config = ShdiViewpointConfig(
            source_path=source,
            crosswalk_path=crosswalk,
            output_path=output,
            ledger_path=tmp_path / "ledger.jsonl",
            variables=SAMPLE_VARIABLES,
            start_year=2020,
            end_year=2020,
        )

        result = build_shdi_v1(config)
        assert result.n_events_output > 0

    def test_year_outside_range_filtered(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.shdi_v1 import (
            ShdiViewpointConfig,
            build_shdi_v1,
        )

        source = tmp_path / "source.parquet"
        crosswalk = tmp_path / "gdl_to_pgid.parquet"
        output = tmp_path / "shdi_v1.parquet"

        _write_source(
            source,
            regions=["NORr101"],
            years=[2019, 2020],
            variables=SAMPLE_VARIABLES,
        )
        _write_crosswalk(crosswalk)

        config = ShdiViewpointConfig(
            source_path=source,
            crosswalk_path=crosswalk,
            output_path=output,
            ledger_path=tmp_path / "ledger.jsonl",
            variables=SAMPLE_VARIABLES,
            start_year=2020,
            end_year=2020,
        )

        result = build_shdi_v1(config)
        assert result.n_filtered == 1
        # NORr101 has 2 pgids × 1 year × 12 months = 24
        assert result.n_events_output == 24

    def test_crosswalk_region_not_in_source_no_crash(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.shdi_v1 import (
            ShdiViewpointConfig,
            build_shdi_v1,
        )

        source = tmp_path / "source.parquet"
        crosswalk = tmp_path / "gdl_to_pgid.parquet"
        output = tmp_path / "shdi_v1.parquet"

        # Source only has NORr101, crosswalk has NORr101 + SWEr201
        _write_source(
            source,
            regions=["NORr101"],
            years=[2020],
            variables=SAMPLE_VARIABLES,
        )
        _write_crosswalk(crosswalk)

        config = ShdiViewpointConfig(
            source_path=source,
            crosswalk_path=crosswalk,
            output_path=output,
            ledger_path=tmp_path / "ledger.jsonl",
            variables=SAMPLE_VARIABLES,
            start_year=2020,
            end_year=2020,
        )

        result = build_shdi_v1(config)
        assert result.n_events_output == 24

    def test_single_year_produces_twelve_rows(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.shdi_v1 import (
            ShdiViewpointConfig,
            build_shdi_v1,
        )

        source = tmp_path / "source.parquet"
        crosswalk = tmp_path / "gdl_to_pgid.parquet"
        output = tmp_path / "shdi_v1.parquet"

        # Single region with 1 pgid
        cw = pa.table({
            "gid": pa.array([1], type=pa.int32()),
            "gdl_code": pa.array(["TST"], type=pa.string()),
        })
        pq.write_table(cw, crosswalk)

        _write_source(
            source,
            regions=["TST"],
            years=[2020],
            variables=SAMPLE_VARIABLES,
        )

        config = ShdiViewpointConfig(
            source_path=source,
            crosswalk_path=crosswalk,
            output_path=output,
            ledger_path=tmp_path / "ledger.jsonl",
            variables=SAMPLE_VARIABLES,
            start_year=2020,
            end_year=2020,
        )

        result = build_shdi_v1(config)
        assert result.n_events_output == 12


# ===================================================================
# RED — Failure handling
# ===================================================================


class TestBuildShdiV1Red:
    """Failure paths."""

    def test_missing_source_raises(self, tmp_path: Path) -> None:
        from datafactory_viewpoint.builders.shdi_v1 import (
            ShdiViewpointConfig,
            build_shdi_v1,
        )

        crosswalk = tmp_path / "gdl_to_pgid.parquet"
        _write_crosswalk(crosswalk)

        config = ShdiViewpointConfig(
            source_path=tmp_path / "nonexistent.parquet",
            crosswalk_path=crosswalk,
            output_path=tmp_path / "out.parquet",
            ledger_path=tmp_path / "ledger.jsonl",
            variables=SAMPLE_VARIABLES,
        )

        with pytest.raises(FileNotFoundError):
            build_shdi_v1(config)

    def test_missing_crosswalk_raises(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.shdi_v1 import (
            ShdiViewpointConfig,
            build_shdi_v1,
        )

        source = tmp_path / "source.parquet"
        _write_source(source, variables=SAMPLE_VARIABLES)

        config = ShdiViewpointConfig(
            source_path=source,
            crosswalk_path=tmp_path / "nonexistent.parquet",
            output_path=tmp_path / "out.parquet",
            ledger_path=tmp_path / "ledger.jsonl",
            variables=SAMPLE_VARIABLES,
        )

        with pytest.raises(FileNotFoundError):
            build_shdi_v1(config)

    def test_empty_version_raises(self) -> None:
        from datafactory_viewpoint.builders.shdi_v1 import (
            ShdiViewpointConfig,
        )

        with pytest.raises(ValueError, match="version"):
            ShdiViewpointConfig(version="")

    def test_empty_variables_raises(self) -> None:
        from datafactory_viewpoint.builders.shdi_v1 import (
            ShdiViewpointConfig,
        )

        with pytest.raises(ValueError, match="variables"):
            ShdiViewpointConfig(variables=())

    def test_start_year_before_epoch_raises(self) -> None:
        from datafactory_viewpoint.builders.shdi_v1 import (
            ShdiViewpointConfig,
        )

        with pytest.raises(ValueError, match="epoch"):
            ShdiViewpointConfig(start_year=1970)

    def test_end_before_start_raises(self) -> None:
        from datafactory_viewpoint.builders.shdi_v1 import (
            ShdiViewpointConfig,
        )

        with pytest.raises(ValueError, match="end_year"):
            ShdiViewpointConfig(
                start_year=2020, end_year=2019,
            )


# ===================================================================
# GREEN — Registry
# ===================================================================


class TestShdiViewpointRegistryGreen:
    """Builder auto-registration."""

    def test_registered_in_builder_registry(self) -> None:
        import datafactory_viewpoint.builders.shdi_v1  # noqa: F401
        from datafactory_viewpoint.builders import list_builders

        assert "shdi_v1" in list_builders()
