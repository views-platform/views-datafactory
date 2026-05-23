"""Falsification stubs: GHS-BUILT-S silent failure modes.

Source: /falsify coverage parity audit 2026-05-22
GHS-BUILT-S-specific tests for offset bounds, empty interpolation,
and config validation gaps. No GHS-POP equivalent.
"""

from __future__ import annotations

import numpy as np
import pytest


class TestF1OffsetBounds:
    """_aggregate_with_alignment must not crash on extreme offsets."""

    def test_extreme_row_offset_no_crash(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            _aggregate_with_alignment,
        )

        data = np.ones((60, 60), dtype=np.uint32) * 100
        grid = _aggregate_with_alignment(data, 999999, 0)

        assert grid.sum() == 0.0
        assert grid.shape == (360, 720)

    def test_extreme_col_offset_no_crash(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            _aggregate_with_alignment,
        )

        data = np.ones((60, 60), dtype=np.uint32) * 100
        grid = _aggregate_with_alignment(data, 0, 999999)

        assert grid.sum() == 0.0
        assert grid.shape == (360, 720)

    def test_negative_offset_no_crash(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            _aggregate_with_alignment,
        )

        data = np.ones((60, 60), dtype=np.uint32) * 100
        grid = _aggregate_with_alignment(data, -999999, 0)

        assert grid.sum() == 0.0
        assert grid.shape == (360, 720)


class TestF2EmptyInterpolation:
    """_interpolate_temporal must handle empty epoch dict."""

    def test_empty_epochs_returns_zeros(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            _interpolate_temporal,
        )

        result = _interpolate_temporal(
            {},
            strategy="linear",
            start_year=2000,
            start_month=1,
            end_year=2000,
            end_month=12,
        )

        assert len(result) == 12
        assert all(v == 0.0 for v in result)


class TestF3ConfigGap:
    """Document that start_year > end_year is currently accepted."""

    def test_reversed_years_accepted(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
        )

        cfg = GhsBuiltSViewpointConfig(
            source_dir=pytest.importorskip("pathlib").Path("data"),
            start_year=2030,
            end_year=1975,
        )
        assert cfg.start_year > cfg.end_year
