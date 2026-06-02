"""Falsification tests for deployment documentation.

Generated: 2026-05-28
Claim: The deployment procedure is clearly documented in README and guides.

Original audit found 1 hard + 2 soft falsifications. All three resolved:
P-1: README now shows assemble_grid.py with all source flags.
P-3: server_operations.md now warns about silent-skip behavior.
P-5: server_operations.md now has a "Run individual pipeline steps" section.
"""

from __future__ import annotations

import re
from pathlib import Path


class TestP1ReadmeAssemblyInvocation:
    """README Quick Start must show the correct assembly invocation
    with all source flags, or clearly state that the bare invocation
    produces a UCDP-only grid.
    """

    def test_readme_assembly_shows_source_flags(self) -> None:
        readme = Path("README.md").read_text()
        quick_start = readme.split("## Quick Start")[1].split("##")[0]

        assert "assemble_grid" in quick_start, (
            "assemble_grid.py not found in Quick Start"
        )

        has_flag = bool(
            re.search(r"--(?:acled|ghspop|ghsbuilts|vdem)-grid", quick_start)
        )
        assert has_flag, (
            "README Quick Start shows assemble_grid.py without source flags. "
            "Bare invocation produces UCDP + static + admin only "
            "(~42 features, not ~75)."
        )


class TestP3SilentSkipDocumented:
    """At least one guide must document that omitting source flags
    causes assembly to silently skip those sources.
    """

    def test_guide_warns_about_silent_skip(self) -> None:
        guides_dir = Path("docs/guides")
        readme = Path("README.md")

        search_files = list(guides_dir.glob("*.md")) + [readme]
        warning_found = False

        for doc in search_files:
            text = doc.read_text()
            paragraphs = re.split(r"\n\n+", text)
            for para in paragraphs:
                lower = para.lower()
                if "assemble" in lower and re.search(
                    r"omit|silently\s+skip|without.*flag.*skip|"
                    r"partial\s+grid|missing\s+source",
                    lower,
                ):
                    warning_found = True
                    break
            if warning_found:
                break

        assert warning_found, (
            "No guide warns that assemble_grid.py silently skips sources "
            "when their --<source>-grid flag is omitted. The CLI --help "
            "says 'omit to skip' but no guide explains the consequence: "
            "a partial grid with no error."
        )


class TestP5ManualDeploymentGuide:
    """A single guide should walk through manual deployment steps
    (individual scripts, not just refresh_pipeline.sh).
    """

    def test_single_guide_covers_manual_deployment(self) -> None:
        guides_dir = Path("docs/guides")
        found = False

        for doc in guides_dir.glob("*.md"):
            text = doc.read_text()
            has_vdem_pipeline = "run_vdem_pipeline" in text
            has_assembly_flags = "--acled-grid" in text or "--vdem-grid" in text
            has_export = "export_zarr" in text
            has_health = "check_health" in text

            if (
                has_vdem_pipeline
                and has_assembly_flags
                and has_export
                and has_health
            ):
                found = True
                break

        assert found, (
            "No single guide covers the full manual deployment sequence: "
            "run source pipelines → assemble with all flags → export → "
            "health check. The information is scattered across README, "
            "deployment guide, server operations, and sprint plans."
        )
