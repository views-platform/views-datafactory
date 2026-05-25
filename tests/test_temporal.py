"""Direct tests for datafactory_viewpoint.temporal."""

from __future__ import annotations

import pytest

from datafactory_viewpoint.temporal import (
    VALID_TEMPORAL_INTERPOLATIONS,
    interpolate_temporal,
)


def test_interpolate_linear_length_and_boundaries() -> None:
    """Linear interpolation of 3 epochs produces correct monthly count."""
    epoch_values = {2000: 10.0, 2005: 20.0, 2010: 30.0}
    result = interpolate_temporal(
        epoch_values,
        strategy="linear",
        start_year=2000,
        start_month=1,
        end_year=2010,
        end_month=12,
    )
    assert len(result) == 132  # 11 years * 12 months
    assert result[0] == pytest.approx(10.0)
    assert result[-1] == pytest.approx(30.0)


def test_interpolate_unknown_strategy_raises() -> None:
    """Unknown strategy string raises ValueError."""
    with pytest.raises(ValueError, match="Unknown"):
        interpolate_temporal(
            {2000: 1.0},
            strategy="cubic_spline",
            start_year=2000,
            start_month=1,
            end_year=2000,
            end_month=12,
        )


def test_valid_strategies_is_nonempty() -> None:
    """VALID_TEMPORAL_INTERPOLATIONS contains at least step and linear."""
    assert "step" in VALID_TEMPORAL_INTERPOLATIONS
    assert "linear" in VALID_TEMPORAL_INTERPOLATIONS
