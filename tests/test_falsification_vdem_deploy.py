"""Falsification stubs: V-Dem deployment readiness.

Source: Sprint 1 — V-Dem production readiness (C-204, Tier 3).
Verifies pipeline wiring, source registry, assembly integration,
deployment guide coverage, and version state.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


class TestF1PipelineWiring:
    """refresh_pipeline.sh must wire V-Dem harvest and compile steps."""

    def test_refresh_pipeline_has_vdem_harvest(self) -> None:
        script = Path("scripts/refresh_pipeline.sh").read_text()
        assert "harvest_vdem" in script, (
            "refresh_pipeline.sh does not reference V-Dem harvest"
        )

    def test_refresh_pipeline_has_vdem_compile(self) -> None:
        script = Path("scripts/refresh_pipeline.sh").read_text()
        assert "vdem" in script.lower(), (
            "refresh_pipeline.sh does not reference V-Dem"
        )
        assert "compile" in script.lower(), (
            "refresh_pipeline.sh does not reference compilation"
        )


class TestF2SourceRegistry:
    """Source registry must include V-Dem with 22 features."""

    def test_source_registry_has_vdem(self) -> None:
        from datafactory_provenance.source_registry import PIPELINE_SOURCES

        vdem = [s for s in PIPELINE_SOURCES if s.name == "V-Dem"]
        assert len(vdem) == 1, (
            f"Expected 1 V-Dem entry in SOURCES, found {len(vdem)}"
        )
        assert len(vdem[0].features) == 22, (
            f"V-Dem should have 22 features, has {len(vdem[0].features)}"
        )


class TestF3AssemblyIntegration:
    """assemble_grid.py must accept --vdem-grid."""

    def test_assembly_has_vdem_grid_arg(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/assemble_grid.py", "--help"],
            capture_output=True, text=True,
        )
        assert "--vdem-grid" in result.stdout, (
            "assemble_grid.py does not accept --vdem-grid"
        )


class TestF4DeploymentGuide:
    """Deployment guide must mention V-Dem."""

    def test_deployment_guide_mentions_vdem(self) -> None:
        guide = Path("docs/guides/hetzner_deployment_guide.md")
        assert guide.exists(), "Missing hetzner_deployment_guide.md"
        text = guide.read_text()
        assert "V-Dem" in text, (
            "Deployment guide does not mention V-Dem"
        )


class TestF5CompileScript:
    """Both compilation paths must set fill_value=NaN (C-205)."""

    def test_compile_script_uses_nan_fill(self) -> None:
        script = Path("scripts/compile_vdem.py").read_text()
        assert "fill_value" in script, (
            "compile_vdem.py does not set fill_value — "
            "V-Dem requires NaN fill (C-205)"
        )
        assert "nan" in script.lower(), (
            "compile_vdem.py fill_value is not NaN — "
            "V-Dem requires NaN fill (C-205)"
        )

    def test_pipeline_runner_uses_nan_fill(self) -> None:
        script = Path("scripts/run_vdem_pipeline.py").read_text()
        assert "fill_value" in script, (
            "run_vdem_pipeline.py does not set fill_value — "
            "production path uses 0.0 default (C-205)"
        )
        assert "nan" in script.lower(), (
            "run_vdem_pipeline.py fill_value is not NaN — "
            "production path would silently convert NaN→0.0"
        )


class TestF6VersionBump:
    """Current version should not already be tagged."""

    @pytest.mark.xfail(reason="Version bump deferred to ship-it")
    def test_version_not_already_tagged(self) -> None:
        from importlib.metadata import version

        current = version("views-datafactory")
        result = subprocess.run(
            ["git", "tag", "-l", f"v{current}"],
            capture_output=True, text=True,
        )
        existing = [t for t in result.stdout.strip().split("\n") if t]
        assert f"v{current}" not in existing, (
            f"Version v{current} is already tagged — "
            f"bump version before shipping"
        )
