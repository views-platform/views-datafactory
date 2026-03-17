"""Specification tests for datafactory_grid contracts.

These tests define the contracts described in src/datafactory_grid/ARCHITECTURE.md
BEFORE the implementation exists. They activate when GridConfig and TemporalConfig
are implemented and exported from datafactory_grid.

Based on proven patterns from views-metric-lab/tests/test_grid.py (508 lines).
"""

from __future__ import annotations

import pytest

# --- Skip infrastructure ---
# Tests skip gracefully until the classes are implemented and exported.

try:
    from datafactory_grid import GridConfig  # type: ignore[attr-defined]

    HAS_GRID_CONFIG = True
except ImportError:
    HAS_GRID_CONFIG = False

try:
    from datafactory_grid import TemporalConfig  # type: ignore[attr-defined]

    HAS_TEMPORAL_CONFIG = True
except ImportError:
    HAS_TEMPORAL_CONFIG = False

skip_no_grid = pytest.mark.skipif(
    not HAS_GRID_CONFIG,
    reason="GridConfig not yet implemented in datafactory_grid",
)
skip_no_temporal = pytest.mark.skipif(
    not HAS_TEMPORAL_CONFIG,
    reason="TemporalConfig not yet implemented in datafactory_grid",
)


# ============================================================
# GridConfig specification tests
# ============================================================


@skip_no_grid
class TestGridConfigDefaults:
    """Default GridConfig must reproduce the standard PRIO-GRID."""

    def test_default_cell_count(self) -> None:
        cfg = GridConfig()
        assert cfg.n_cells == 259_200, "Default PRIO-GRID: 360 x 720 = 259,200"

    def test_default_nrow(self) -> None:
        cfg = GridConfig()
        assert cfg.nrow == 360

    def test_default_ncol(self) -> None:
        cfg = GridConfig()
        assert cfg.ncol == 720

    def test_default_resolution(self) -> None:
        cfg = GridConfig()
        assert cfg.resolution == 0.5


@skip_no_grid
class TestGridConfigCustomResolution:
    """Custom resolution must produce correct dimensions."""

    def test_quarter_degree(self) -> None:
        cfg = GridConfig(resolution=0.25)
        assert cfg.nrow == 720
        assert cfg.ncol == 1440
        assert cfg.n_cells == 1_036_800


@skip_no_grid
class TestGridConfigValidation:
    """GridConfig __post_init__ must reject invalid parameters."""

    def test_rejects_zero_resolution(self) -> None:
        with pytest.raises(ValueError, match="[Rr]esolution"):
            GridConfig(resolution=0.0)

    def test_rejects_negative_resolution(self) -> None:
        with pytest.raises(ValueError, match="[Rr]esolution"):
            GridConfig(resolution=-0.5)

    def test_rejects_west_ge_east(self) -> None:
        with pytest.raises(ValueError, match="[Ww]est"):
            GridConfig(west=180.0, east=-180.0)

    def test_rejects_south_ge_north(self) -> None:
        with pytest.raises(ValueError, match="[Ss]outh"):
            GridConfig(south=90.0, north=-90.0)

    def test_rejects_indivisible_resolution(self) -> None:
        with pytest.raises(ValueError, match="[Rr]esolution"):
            GridConfig(resolution=0.7)

    def test_frozen(self) -> None:
        cfg = GridConfig()
        with pytest.raises(AttributeError):
            cfg.resolution = 1.0  # type: ignore[misc]


# ============================================================
# TemporalConfig specification tests
# ============================================================


@skip_no_temporal
class TestTemporalConfigDefaults:
    """Default TemporalConfig must produce the standard backbone."""

    def test_default_n_steps(self) -> None:
        cfg = TemporalConfig()
        assert cfg.n_steps == 432, "1989-01 to 2024-12 inclusive = 432 months"


@skip_no_temporal
class TestTemporalConfigValidation:
    """TemporalConfig __post_init__ must reject invalid parameters."""

    def test_rejects_start_after_end(self) -> None:
        with pytest.raises(ValueError, match="start.*after|after.*end|start_year"):
            TemporalConfig(start_year=2025, end_year=2024)

    def test_rejects_month_below_1(self) -> None:
        with pytest.raises(ValueError, match="[Mm]onth"):
            TemporalConfig(start_month=0)

    def test_rejects_month_above_12(self) -> None:
        with pytest.raises(ValueError, match="[Mm]onth"):
            TemporalConfig(end_month=13)

    def test_rejects_negative_year(self) -> None:
        with pytest.raises(ValueError, match="[Yy]ear"):
            TemporalConfig(start_year=-1)

    def test_frozen(self) -> None:
        cfg = TemporalConfig()
        with pytest.raises(AttributeError):
            cfg.start_year = 2000  # type: ignore[misc]
