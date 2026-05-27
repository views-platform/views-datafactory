"""Falsification stubs: V-Dem visual audit capability.

Source: /falsify audit 2026-05-26
Claim: "For each of the features added through the V-Dem data source,
        we have at least as thorough visual audit tools (maps, plots,
        timelines, etc.) as we do for each of the other data sources."

All 10 probes falsified the claim. V-Dem has zero visual audit
infrastructure while ACLED, GHS-BUILT-S, and GHS-POP each have
10-14 dedicated plots. These stubs encode what must exist before the
claim can be reasserted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
REPORTS_DIR = Path(__file__).parent.parent / "reports"


class TestF1VerifyScriptExists:
    """F1: A verify_vdem_grid.py script must exist."""

    def test_verify_script_exists(self) -> None:
        candidates = [
            SCRIPTS_DIR / "verify_vdem_grid.py",
            SCRIPTS_DIR / "verify_vdem.py",
            SCRIPTS_DIR / "audit_vdem.py",
        ]
        assert any(c.exists() for c in candidates), (
            "No V-Dem verify/audit script found "
            "(peers: verify_acled_grid.py, "
            "verify_ghsbuilts_grid.py, verify_ghspop_grid.py)"
        )


class TestF2VisualOutputCapability:
    """F2: Some script must produce visual output from V-Dem data."""

    def test_plotting_references_in_vdem_scripts(self) -> None:
        plotting_keywords = {
            "matplotlib", "imshow", "savefig", "pyplot",
            "save_plot", "Figure",
        }
        vdem_keywords = {
            "vdem", "v2x_", "V-Dem", "democracy",
        }

        matches = []
        for py_file in SCRIPTS_DIR.glob("*.py"):
            content = py_file.read_text()
            has_plot = any(kw in content for kw in plotting_keywords)
            has_vdem = any(kw in content for kw in vdem_keywords)
            if has_plot and has_vdem:
                matches.append(py_file.name)

        assert matches, (
            "No script combines V-Dem data with plotting"
        )


class TestF3SpatialMapsParity:
    """F3: V-Dem audit must include spatial maps (peers have 7+ each)."""

    def test_verify_script_has_spatial_maps(self) -> None:
        script = SCRIPTS_DIR / "verify_vdem_grid.py"
        if not script.exists():
            pytest.fail(
                "verify_vdem_grid.py missing — "
                "cannot check spatial maps"
            )
        content = script.read_text()
        spatial_kw = [
            "spatial_imshow", "imshow", "pcolormesh",
        ]
        count = sum(
            content.count(kw) for kw in spatial_kw
        )
        assert count >= 3, (
            f"V-Dem audit has {count} spatial map calls "
            f"(peers have 7+)"
        )


class TestF4TemporalChartsParity:
    """F4: V-Dem audit must include temporal plots."""

    def test_verify_script_has_temporal_charts(self) -> None:
        script = SCRIPTS_DIR / "verify_vdem_grid.py"
        if not script.exists():
            pytest.fail(
                "verify_vdem_grid.py missing — "
                "cannot check temporal charts"
            )
        content = script.read_text()
        assert "save_plot" in content or "savefig" in content, (
            "V-Dem audit script has no save_plot/savefig calls"
        )


class TestF5ConcentrationAnalysis:
    """F5: V-Dem audit must include Lorenz/Gini concentration."""

    def test_verify_script_has_concentration(self) -> None:
        script = SCRIPTS_DIR / "verify_vdem_grid.py"
        if not script.exists():
            pytest.fail(
                "verify_vdem_grid.py missing — "
                "cannot check concentration analysis"
            )
        content = script.read_text().lower()
        assert "lorenz" in content or "gini" in content, (
            "V-Dem audit lacks Lorenz/Gini concentration "
            "(all peers have it)"
        )


class TestF6SpotChecks:
    """F6: V-Dem audit must include ground-truth spot checks."""

    def test_verify_script_has_spot_checks(self) -> None:
        script = SCRIPTS_DIR / "verify_vdem_grid.py"
        if not script.exists():
            pytest.fail(
                "verify_vdem_grid.py missing — "
                "cannot check spot checks"
            )
        content = script.read_text().lower()
        assert "spot" in content or "ground" in content, (
            "V-Dem audit lacks ground-truth spot checks "
            "(all peers have them)"
        )


class TestF7TrajectoryPlots:
    """F7: V-Dem audit must include cell trajectory plots."""

    def test_verify_script_has_trajectories(self) -> None:
        script = SCRIPTS_DIR / "verify_vdem_grid.py"
        if not script.exists():
            pytest.fail(
                "verify_vdem_grid.py missing — "
                "cannot check trajectories"
            )
        content = script.read_text().lower()
        assert "trajector" in content, (
            "V-Dem audit lacks trajectory plots "
            "(all peers have 4x3 panels)"
        )


class TestF8PipelineIntegration:
    """F8: Pipeline must include a verify/audit step."""

    def test_pipeline_has_verify_step(self) -> None:
        pipeline = SCRIPTS_DIR / "run_vdem_pipeline.py"
        assert pipeline.exists(), "Pipeline script missing"

        content = pipeline.read_text()
        verify_indicators = [
            "verify", "audit", "plot", "visual",
            "verify_vdem", "save_plot",
        ]
        assert any(kw in content for kw in verify_indicators), (
            "run_vdem_pipeline.py has no verify/audit step "
            "(peers wire verify into their pipeline runners)"
        )


class TestF9TestGateExists:
    """F9: Falsification test for visual audit must exist."""

    def test_this_file_has_peers(self) -> None:
        test_dir = Path(__file__).parent
        peer = (
            test_dir / "test_falsification_ghsbuilts_visual_audit.py"
        )
        assert peer.exists(), (
            "Peer falsification test missing — "
            "test gate comparison impossible"
        )


class TestF10PerFeatureVisualization:
    """F10: V-Dem audit must visualize per-feature breakdowns."""

    def test_verify_script_has_per_feature_plots(self) -> None:
        script = SCRIPTS_DIR / "verify_vdem_grid.py"
        if not script.exists():
            pytest.fail(
                "verify_vdem_grid.py missing — "
                "cannot check per-feature plots"
            )
        content = script.read_text()
        assert "v2x_" in content or "feature" in content.lower(), (
            "V-Dem audit does not show per-feature breakdown "
            "(ACLED does per-type maps for 6 types; "
            "V-Dem has 22 features)"
        )
