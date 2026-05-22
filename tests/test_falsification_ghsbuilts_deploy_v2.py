"""Falsification stubs: GHS-BUILT-S deployment readiness (round 2).

Source: /falsify coverage parity audit 2026-05-22
Verifies deployment-critical files, CLI interface, version state.
"""

from __future__ import annotations

import subprocess
import sys


class TestF1UncommittedFixes:
    """No uncommitted changes in GHS-BUILT-S deployment files."""

    def test_no_uncommitted_deployment_files(self) -> None:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--",
             "src/datafactory_viewpoint/builders/ghsbuilts_v1.py",
             "src/datafactory_provenance/source_registry.py",
             ".gitignore"],
            capture_output=True, text=True,
        )
        dirty = [f for f in result.stdout.strip().split("\n") if f]
        assert not dirty, (
            f"Deployment-critical files have uncommitted changes: "
            f"{dirty} — commit before tagging"
        )


class TestF2TemporalEndYear:
    """Pipeline script must accept --end-year."""

    def test_pipeline_accepts_end_year(self) -> None:
        result = subprocess.run(
            [sys.executable,
             "scripts/run_ghsbuilts_pipeline.py", "--help"],
            capture_output=True, text=True,
        )
        assert "--end-year" in result.stdout, (
            "run_ghsbuilts_pipeline.py does not accept --end-year "
            "— C-175 footgun: bare TemporalConfig() defaults to "
            "end_year=2024"
        )


class TestF3VersionBump:
    """Current version should not already be tagged."""

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
