"""Falsification stubs: GHS-BUILT-S temporal interpolation integrity.

Source: /falsify coverage parity audit 2026-05-22
Verifies month_id VIEWS convention, contiguity, monotonicity,
and step-function epoch boundaries.
"""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq


class TestF1MonthId:
    """Month IDs must follow the VIEWS convention."""

    def test_month_id_january_1980_is_1(
        self, tmp_path: Path,
    ) -> None:
        from test_ghsbuilts_viewpoint import (
            _make_uniform_raster,
        )

        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
            build_ghsbuilts_v1,
        )

        source_dir = tmp_path / "raw"
        source_dir.mkdir()
        _make_uniform_raster(
            source_dir
            / "GHS_BUILT_S_E1980_GLOBE_R2023A_4326_30ss_V1_0.tif",
            value=100,
            prio_rows=1,
            prio_cols=1,
        )

        config = GhsBuiltSViewpointConfig(
            source_dir=source_dir,
            output_path=tmp_path / "out.parquet",
            ledger_path=tmp_path / "ledger.jsonl",
            epochs=(1980,),
            start_year=1980,
            start_month=1,
            end_year=1980,
            end_month=1,
        )
        result = build_ghsbuilts_v1(config)
        table = pq.read_table(result.output_path)

        month_ids = table.column("month_id").to_pylist()
        assert 1 in month_ids, (
            "January 1980 should have month_id=1"
        )

    def test_month_ids_contiguous(self, tmp_path: Path) -> None:
        from test_ghsbuilts_viewpoint import (
            _two_epoch_config,
        )

        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(
            tmp_path,
            value_a=100,
            value_b=200,
            prio_rows=1,
            prio_cols=1,
        )
        result = build_ghsbuilts_v1(config)
        table = pq.read_table(result.output_path)

        pgid = table.column("pgid").to_pylist()[0]
        mids = sorted(
            m for p, m in zip(
                table.column("pgid").to_pylist(),
                table.column("month_id").to_pylist(),
                strict=True,
            )
            if p == pgid
        )

        for i in range(1, len(mids)):
            assert mids[i] == mids[i - 1] + 1, (
                f"Gap at {mids[i-1]} -> {mids[i]}"
            )


class TestF2Monotonicity:
    """Interpolated values must be monotonic for increasing epochs."""

    def test_linear_monotonic_between_increasing_epochs(
        self, tmp_path: Path,
    ) -> None:
        from test_ghsbuilts_viewpoint import (
            _two_epoch_config,
        )

        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(
            tmp_path,
            value_a=100,
            value_b=500,
            prio_rows=1,
            prio_cols=1,
        )
        result = build_ghsbuilts_v1(config)
        table = pq.read_table(result.output_path)

        pgid = table.column("pgid").to_pylist()[0]
        pairs = sorted(
            (m, v)
            for p, m, v in zip(
                table.column("pgid").to_pylist(),
                table.column("month_id").to_pylist(),
                table.column("built_area").to_pylist(),
                strict=True,
            )
            if p == pgid
        )

        values = [v for _, v in pairs]
        for i in range(1, len(values)):
            assert values[i] >= values[i - 1], (
                f"Non-monotonic at month {i}: "
                f"{values[i]} < {values[i-1]}"
            )

    def test_step_changes_only_at_epoch_boundaries(
        self, tmp_path: Path,
    ) -> None:
        from test_ghsbuilts_viewpoint import (
            _two_epoch_config,
        )

        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(
            tmp_path,
            value_a=100,
            value_b=200,
            prio_rows=1,
            prio_cols=1,
            temporal_interpolation="step",
        )
        result = build_ghsbuilts_v1(config)
        table = pq.read_table(result.output_path)

        pgid = table.column("pgid").to_pylist()[0]
        pairs = sorted(
            (m, v)
            for p, m, v in zip(
                table.column("pgid").to_pylist(),
                table.column("month_id").to_pylist(),
                table.column("built_area").to_pylist(),
                strict=True,
            )
            if p == pgid
        )

        values = [v for _, v in pairs]
        unique_values = set(values)
        assert len(unique_values) == 2, (
            f"Expected exactly 2 distinct values for step "
            f"interpolation with 2 epochs, got {len(unique_values)}"
        )
