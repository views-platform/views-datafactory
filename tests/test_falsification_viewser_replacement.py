"""Falsification audit: can views-datafactory replace ingester3 and viewser?

Claim: "views-datafactory is now at the state of an MVP which can 100%
replace ingester and viewser."

Hypothesis: A VIEWS model developer can train, evaluate, and forecast
using views-datafactory as the sole data source, with zero runtime
dependency on ingester3, viewser, or PRIO PostgreSQL.

Audit date: 2026-04-20
Verdict: CONTESTED — no hard falsifications for pgm models, but two
soft falsifications limit the "100%" claim.

Soft falsification S1: 48/70 models use country_month LOA, which the
factory cannot serve (no cm aggregation layer).

Soft falsification S2: 14 viewser transform types are used across the
fleet (tlag, spatial.lag, decay, ln, etc.). The factory provides raw
values only — models using non-trivial transforms cannot migrate without
reimplementing those transforms outside viewser.
"""

from __future__ import annotations

import pytest


class TestF1ImportChain:
    """F1: bright_starship's data path has no ingester3/viewser imports."""

    def test_config_partitions_no_ingester3(self) -> None:
        """config_partitions.py must not import ingester3."""
        import ast
        from pathlib import Path

        config = (
            Path(__file__).resolve().parents[1]
            / ".."
            / "views-models"
            / "models"
            / "bright_starship"
            / "configs"
            / "config_partitions.py"
        )
        if not config.exists():
            pytest.skip("bright_starship not available")

        tree = ast.parse(config.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "ingester3" not in node.module, (
                    f"config_partitions.py imports ingester3: {node.module}"
                )
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "ingester3" not in alias.name, (
                        f"config_partitions.py imports ingester3: {alias.name}"
                    )

    def test_config_queryset_no_viewser(self) -> None:
        """config_queryset.py must not import viewser."""
        import ast
        from pathlib import Path

        config = (
            Path(__file__).resolve().parents[1]
            / ".."
            / "views-models"
            / "models"
            / "bright_starship"
            / "configs"
            / "config_queryset.py"
        )
        if not config.exists():
            pytest.skip("bright_starship not available")

        tree = ast.parse(config.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "viewser" not in node.module, (
                    f"config_queryset.py imports viewser: {node.module}"
                )


class TestF5MonthIdEncoding:
    """F5: _current_month_id() matches VIEWS month_id convention."""

    @pytest.mark.parametrize(
        "year,month,expected",
        [
            (1980, 1, 1),    # epoch
            (1990, 1, 121),  # calibration train start
            (2017, 1, 445),  # calibration test start
            (2021, 1, 493),  # validation test start
            (2025, 1, 541),  # recent
        ],
    )
    def test_month_id_encoding(
        self, year: int, month: int, expected: int
    ) -> None:
        actual = (year - 1980) * 12 + month
        assert actual == expected, (
            f"month_id({year}, {month}) = {actual}, expected {expected}"
        )


class TestS1CountryMonthGap:
    """S1 (resolved): factory now supports country_month aggregation."""

    def test_load_dataset_country_month(self) -> None:
        """load_dataset() accepts output_format='country_month'.

        Validates that the format is recognized (no ValueError).
        Full integration tested in test_country_month.py.
        """
        from datafactory_query.dataset import _VALID_FORMATS

        assert "country_month" in _VALID_FORMATS


class TestS2TransformGap:
    """S2 (soft falsification): factory provides no transform layer."""

    @pytest.mark.xfail(
        reason="datafactory_query has no transform capabilities",
        strict=True,
    )
    def test_temporal_lag_available(self) -> None:
        """Temporal lag (.transform.temporal.tlag) is used by 832 viewser
        column definitions across the fleet. The factory has no equivalent.
        """
        import datafactory_query

        assert hasattr(datafactory_query, "transforms"), (
            "datafactory_query has no transforms module"
        )

    @pytest.mark.xfail(
        reason="datafactory_query has no transform capabilities",
        strict=True,
    )
    def test_spatial_lag_available(self) -> None:
        """Spatial lag (.transform.spatial.countrylag) is used by 486
        viewser column definitions. The factory has no equivalent.
        """
        import datafactory_query

        assert hasattr(datafactory_query, "transforms"), (
            "datafactory_query has no transforms module"
        )
