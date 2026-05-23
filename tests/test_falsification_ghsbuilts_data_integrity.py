"""Falsification stubs: GHS-BUILT-S data integrity.

Source: /falsify coverage parity audit 2026-05-22
Verifies uint32 overflow protection, zero-value semantics,
and output Parquet schema invariants.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest


class TestF1Uint32Safety:
    """Aggregation must produce float64 and handle uint32 max."""

    def test_aggregation_returns_float64(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            _aggregate_with_alignment,
        )

        data = np.ones((60, 60), dtype=np.uint32)
        grid = _aggregate_with_alignment(data, 0, 0)

        assert grid.dtype == np.float64

    def test_max_uint32_no_overflow(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            _aggregate_with_alignment,
        )

        max_val = np.iinfo(np.uint32).max
        data = np.full((60, 60), max_val, dtype=np.uint32)
        grid = _aggregate_with_alignment(data, 0, 0)

        expected = float(max_val) * 60 * 60
        assert grid[0, 0] == pytest.approx(expected, rel=1e-10)


class TestF2ZeroSemantics:
    """Zero built_area must be excluded from viewpoint output."""

    def test_zero_excluded_from_output(
        self, tmp_path: Path,
    ) -> None:
        from test_ghsbuilts_viewpoint import (
            _two_epoch_config,
        )

        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(
            tmp_path, value_a=0, value_b=0,
        )
        result = build_ghsbuilts_v1(config)

        assert result.n_events_output == 0

    def test_nonzero_included_in_output(
        self, tmp_path: Path,
    ) -> None:
        from test_ghsbuilts_viewpoint import (
            _two_epoch_config,
        )

        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(
            tmp_path, value_a=100, value_b=200,
        )
        result = build_ghsbuilts_v1(config)

        assert result.n_events_output > 0


class TestF3Schema:
    """Output Parquet must have exactly three columns."""

    def test_output_columns_exactly_three(
        self, tmp_path: Path,
    ) -> None:
        from test_ghsbuilts_viewpoint import (
            _two_epoch_config,
        )

        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            build_ghsbuilts_v1,
        )

        config, _ = _two_epoch_config(tmp_path)
        result = build_ghsbuilts_v1(config)
        table = pq.read_table(result.output_path)

        assert table.column_names == [
            "pgid", "month_id", "built_area",
        ]
