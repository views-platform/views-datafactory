"""Tests for V-Dem viewpoint builder — country-year to grid-monthly.

Green: happy path (crosswalk, expansion, output format, month_id).
Beige: boundary conditions (unmapped countries, year filtering).
Red: failure handling (missing files, empty output).

Ref: ADR-035 (V-Dem source selection).
"""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_VARIABLES = ("v2x_libdem", "v2xcl_dmove")


def _write_crosswalk(path: Path) -> None:
    """Write a minimal GAUL iso3_code.parquet crosswalk."""
    table = pa.table({
        "gid": pa.array([100, 101, 200, 201, 202], type=pa.int32()),
        "value": pa.array(
            ["NOR", "NOR", "SWE", "SWE", "SWE"],
            type=pa.string(),
        ),
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


def _write_source(
    path: Path,
    *,
    countries: list[str] | None = None,
    years: list[int] | None = None,
    variables: tuple[str, ...] = SAMPLE_VARIABLES,
) -> None:
    """Write a minimal V-Dem harvest Parquet."""
    if countries is None:
        countries = ["NOR", "SWE"]
    if years is None:
        years = [2020, 2021]

    rows_iso3: list[str] = []
    rows_year: list[int] = []
    rows_vals: dict[str, list[float]] = {v: [] for v in variables}

    val = 0.1
    for iso3 in countries:
        for year in years:
            rows_iso3.append(iso3)
            rows_year.append(year)
            for v in variables:
                rows_vals[v].append(round(val, 2))
                val += 0.01

    columns: dict[str, pa.Array] = {
        "country_text_id": pa.array(rows_iso3, type=pa.string()),
        "year": pa.array(rows_year, type=pa.int64()),
    }
    for v in variables:
        columns[v] = pa.array(rows_vals[v], type=pa.float64())

    table = pa.table(columns)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


# ===================================================================
# GREEN — Config
# ===================================================================


class TestVdemViewpointConfigGreen:
    """Config defaults and immutability."""

    def test_defaults(self) -> None:
        from datafactory_viewpoint.builders.vdem_v1 import (
            VdemViewpointConfig,
        )

        cfg = VdemViewpointConfig()
        assert len(cfg.variables) == 22
        assert cfg.start_year == 1980
        assert cfg.end_year == 2025
        assert cfg.version == "vdem_v1"

    def test_frozen(self) -> None:
        from datafactory_viewpoint.builders.vdem_v1 import (
            VdemViewpointConfig,
        )

        cfg = VdemViewpointConfig()
        with pytest.raises(AttributeError):
            cfg.version = "v2"  # type: ignore[misc]


# ===================================================================
# GREEN — Build
# ===================================================================


class TestBuildVdemV1Green:
    """Happy-path viewpoint build."""

    def test_basic_expansion(self, tmp_path: Path) -> None:
        from datafactory_viewpoint.builders.vdem_v1 import (
            VdemViewpointConfig,
            build_vdem_v1,
        )

        source = tmp_path / "source.parquet"
        crosswalk = tmp_path / "iso3_code.parquet"
        output = tmp_path / "vdem_v1.parquet"

        _write_source(source, variables=SAMPLE_VARIABLES)
        _write_crosswalk(crosswalk)

        config = VdemViewpointConfig(
            source_path=source,
            crosswalk_path=crosswalk,
            output_path=output,
            ledger_path=tmp_path / "ledger.jsonl",
            variables=SAMPLE_VARIABLES,
            start_year=2020,
            end_year=2021,
        )

        result = build_vdem_v1(config)

        assert result.output_path == output
        assert output.exists()
        assert result.n_events_input == 4
        # 2 countries × 2 years × 12 months × pgids_per_country
        # NOR has 2 pgids, SWE has 3 pgids → (2+3) × 2 × 12 = 120
        assert result.n_events_output == 120

    def test_output_columns(self, tmp_path: Path) -> None:
        from datafactory_viewpoint.builders.vdem_v1 import (
            VdemViewpointConfig,
            build_vdem_v1,
        )

        source = tmp_path / "source.parquet"
        crosswalk = tmp_path / "iso3_code.parquet"
        output = tmp_path / "vdem_v1.parquet"

        _write_source(source, variables=SAMPLE_VARIABLES)
        _write_crosswalk(crosswalk)

        config = VdemViewpointConfig(
            source_path=source,
            crosswalk_path=crosswalk,
            output_path=output,
            ledger_path=tmp_path / "ledger.jsonl",
            variables=SAMPLE_VARIABLES,
            start_year=2020,
            end_year=2021,
        )

        build_vdem_v1(config)

        table = pq.read_table(output)
        col_names = set(table.column_names)
        assert "pgid" in col_names
        assert "month_id" in col_names
        for var in SAMPLE_VARIABLES:
            assert var in col_names

    def test_values_constant_within_year(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.vdem_v1 import (
            VdemViewpointConfig,
            build_vdem_v1,
        )

        source = tmp_path / "source.parquet"
        crosswalk = tmp_path / "iso3_code.parquet"
        output = tmp_path / "vdem_v1.parquet"

        _write_source(
            source,
            countries=["NOR"],
            years=[2020],
            variables=SAMPLE_VARIABLES,
        )
        _write_crosswalk(crosswalk)

        config = VdemViewpointConfig(
            source_path=source,
            crosswalk_path=crosswalk,
            output_path=output,
            ledger_path=tmp_path / "ledger.jsonl",
            variables=SAMPLE_VARIABLES,
            start_year=2020,
            end_year=2020,
        )

        build_vdem_v1(config)

        table = pq.read_table(output)
        # NOR has pgids 100, 101 → 2 pgids × 12 months = 24 rows
        assert table.num_rows == 24

        # All values for pgid=100 should be identical across months
        pgids = table.column("pgid").to_pylist()
        vals = table.column("v2x_libdem").to_pylist()

        pgid100_vals = [
            v for p, v in zip(pgids, vals, strict=True)
            if p == 100
        ]
        assert len(pgid100_vals) == 12
        assert len(set(pgid100_vals)) == 1

    def test_month_id_calculation(self, tmp_path: Path) -> None:
        from datafactory_viewpoint.builders.vdem_v1 import (
            VdemViewpointConfig,
            build_vdem_v1,
        )

        source = tmp_path / "source.parquet"
        crosswalk = tmp_path / "iso3_code.parquet"
        output = tmp_path / "vdem_v1.parquet"

        # Use a single country with 1 pgid for easy verification
        table = pa.table({
            "gid": pa.array([1], type=pa.int32()),
            "value": pa.array(["TST"], type=pa.string()),
        })
        pq.write_table(table, crosswalk)

        _write_source(
            source,
            countries=["TST"],
            years=[1980],
            variables=SAMPLE_VARIABLES,
        )

        config = VdemViewpointConfig(
            source_path=source,
            crosswalk_path=crosswalk,
            output_path=output,
            ledger_path=tmp_path / "ledger.jsonl",
            variables=SAMPLE_VARIABLES,
            start_year=1980,
            end_year=1980,
        )

        build_vdem_v1(config)

        result_table = pq.read_table(output)
        month_ids = sorted(
            result_table.column("month_id").to_pylist()
        )
        # 1980: month_id 1 (Jan) through 12 (Dec)
        assert month_ids == list(range(1, 13))

    def test_provenance_ledger_written(
        self, tmp_path: Path,
    ) -> None:
        import json

        from datafactory_viewpoint.builders.vdem_v1 import (
            VdemViewpointConfig,
            build_vdem_v1,
        )

        source = tmp_path / "source.parquet"
        crosswalk = tmp_path / "iso3_code.parquet"
        ledger = tmp_path / "ledger.jsonl"

        _write_source(source, variables=SAMPLE_VARIABLES)
        _write_crosswalk(crosswalk)

        config = VdemViewpointConfig(
            source_path=source,
            crosswalk_path=crosswalk,
            output_path=tmp_path / "out.parquet",
            ledger_path=ledger,
            variables=SAMPLE_VARIABLES,
            start_year=2020,
            end_year=2021,
        )

        build_vdem_v1(config)

        assert ledger.exists()
        entries = [
            json.loads(line)
            for line in ledger.read_text().strip().split("\n")
        ]
        assert entries[-1]["outcome"] == "success"
        assert entries[-1]["dataset"] == "vdem_viewpoint"
        assert entries[-1]["n_variables"] == 2

    def test_twelve_months_per_year_per_pgid(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.vdem_v1 import (
            VdemViewpointConfig,
            build_vdem_v1,
        )

        source = tmp_path / "source.parquet"
        crosswalk = tmp_path / "iso3_code.parquet"
        output = tmp_path / "vdem_v1.parquet"

        _write_source(
            source,
            countries=["NOR"],
            years=[2020],
            variables=SAMPLE_VARIABLES,
        )
        _write_crosswalk(crosswalk)

        config = VdemViewpointConfig(
            source_path=source,
            crosswalk_path=crosswalk,
            output_path=output,
            ledger_path=tmp_path / "ledger.jsonl",
            variables=SAMPLE_VARIABLES,
            start_year=2020,
            end_year=2020,
        )

        build_vdem_v1(config)

        table = pq.read_table(output)
        pgids = table.column("pgid").to_pylist()

        # Each pgid should appear exactly 12 times
        from collections import Counter
        pgid_counts = Counter(pgids)
        for pgid, count in pgid_counts.items():
            assert count == 12, (
                f"pgid {pgid} has {count} rows, expected 12"
            )


# ===================================================================
# BEIGE — Boundary conditions
# ===================================================================


class TestBuildVdemV1Beige:
    """Boundary conditions and warnings."""

    def test_unmapped_country_warns_not_crashes(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.vdem_v1 import (
            VdemViewpointConfig,
            build_vdem_v1,
        )

        source = tmp_path / "source.parquet"
        crosswalk = tmp_path / "iso3_code.parquet"
        output = tmp_path / "vdem_v1.parquet"

        # Source has XXX which is not in the crosswalk
        _write_source(
            source,
            countries=["NOR", "XXX"],
            years=[2020],
            variables=SAMPLE_VARIABLES,
        )
        _write_crosswalk(crosswalk)

        config = VdemViewpointConfig(
            source_path=source,
            crosswalk_path=crosswalk,
            output_path=output,
            ledger_path=tmp_path / "ledger.jsonl",
            variables=SAMPLE_VARIABLES,
            start_year=2020,
            end_year=2020,
        )

        result = build_vdem_v1(config)
        # Should still produce output for NOR
        assert result.n_events_output > 0

    def test_year_outside_range_filtered(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.vdem_v1 import (
            VdemViewpointConfig,
            build_vdem_v1,
        )

        source = tmp_path / "source.parquet"
        crosswalk = tmp_path / "iso3_code.parquet"
        output = tmp_path / "vdem_v1.parquet"

        # Source has 2019 data but config starts at 2020
        _write_source(
            source,
            countries=["NOR"],
            years=[2019, 2020],
            variables=SAMPLE_VARIABLES,
        )
        _write_crosswalk(crosswalk)

        config = VdemViewpointConfig(
            source_path=source,
            crosswalk_path=crosswalk,
            output_path=output,
            ledger_path=tmp_path / "ledger.jsonl",
            variables=SAMPLE_VARIABLES,
            start_year=2020,
            end_year=2020,
        )

        result = build_vdem_v1(config)
        assert result.n_filtered == 1
        # NOR has 2 pgids × 1 year × 12 months = 24
        assert result.n_events_output == 24

    def test_gaul_country_not_in_vdem_no_crash(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.vdem_v1 import (
            VdemViewpointConfig,
            build_vdem_v1,
        )

        source = tmp_path / "source.parquet"
        crosswalk = tmp_path / "iso3_code.parquet"
        output = tmp_path / "vdem_v1.parquet"

        # Source only has NOR but crosswalk has NOR + SWE
        _write_source(
            source,
            countries=["NOR"],
            years=[2020],
            variables=SAMPLE_VARIABLES,
        )
        _write_crosswalk(crosswalk)

        config = VdemViewpointConfig(
            source_path=source,
            crosswalk_path=crosswalk,
            output_path=output,
            ledger_path=tmp_path / "ledger.jsonl",
            variables=SAMPLE_VARIABLES,
            start_year=2020,
            end_year=2020,
        )

        result = build_vdem_v1(config)
        # Only NOR rows, no SWE rows
        assert result.n_events_output == 24


# ===================================================================
# RED — Failure handling
# ===================================================================


class TestBuildVdemV1Red:
    """Failure paths."""

    def test_missing_source_raises(self, tmp_path: Path) -> None:
        from datafactory_viewpoint.builders.vdem_v1 import (
            VdemViewpointConfig,
            build_vdem_v1,
        )

        crosswalk = tmp_path / "iso3_code.parquet"
        _write_crosswalk(crosswalk)

        config = VdemViewpointConfig(
            source_path=tmp_path / "nonexistent.parquet",
            crosswalk_path=crosswalk,
            output_path=tmp_path / "out.parquet",
            ledger_path=tmp_path / "ledger.jsonl",
            variables=SAMPLE_VARIABLES,
        )

        with pytest.raises(FileNotFoundError):
            build_vdem_v1(config)

    def test_missing_crosswalk_raises(
        self, tmp_path: Path,
    ) -> None:
        from datafactory_viewpoint.builders.vdem_v1 import (
            VdemViewpointConfig,
            build_vdem_v1,
        )

        source = tmp_path / "source.parquet"
        _write_source(source, variables=SAMPLE_VARIABLES)

        config = VdemViewpointConfig(
            source_path=source,
            crosswalk_path=tmp_path / "nonexistent.parquet",
            output_path=tmp_path / "out.parquet",
            ledger_path=tmp_path / "ledger.jsonl",
            variables=SAMPLE_VARIABLES,
        )

        with pytest.raises(FileNotFoundError):
            build_vdem_v1(config)

    def test_empty_version_raises(self) -> None:
        from datafactory_viewpoint.builders.vdem_v1 import (
            VdemViewpointConfig,
        )

        with pytest.raises(ValueError, match="version"):
            VdemViewpointConfig(version="")

    def test_empty_variables_raises(self) -> None:
        from datafactory_viewpoint.builders.vdem_v1 import (
            VdemViewpointConfig,
        )

        with pytest.raises(ValueError, match="variables"):
            VdemViewpointConfig(variables=())

    def test_start_year_before_epoch_raises(self) -> None:
        from datafactory_viewpoint.builders.vdem_v1 import (
            VdemViewpointConfig,
        )

        with pytest.raises(ValueError, match="epoch"):
            VdemViewpointConfig(start_year=1970)

    def test_end_before_start_raises(self) -> None:
        from datafactory_viewpoint.builders.vdem_v1 import (
            VdemViewpointConfig,
        )

        with pytest.raises(ValueError, match="end_year"):
            VdemViewpointConfig(
                start_year=2020, end_year=2019,
            )


# ===================================================================
# GREEN — Registry
# ===================================================================


class TestVdemViewpointRegistryGreen:
    """Builder auto-registration."""

    def test_registered_in_builder_registry(self) -> None:
        import datafactory_viewpoint.builders.vdem_v1  # noqa: F401
        from datafactory_viewpoint.builders import list_builders

        assert "vdem_v1" in list_builders()
