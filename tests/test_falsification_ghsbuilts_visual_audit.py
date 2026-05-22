"""Falsification stubs: GHS-BUILT-S visual audit capability.

Source: /falsify audit 2026-05-22
Claim: "We have visual audit for GHS-BUILT-S working locally so we
        can see that the downloaded data looks like we think it should."

All 5 probes falsified the claim. These stubs encode what must exist
before the claim can be reasserted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
REPORTS_DIR = Path(__file__).parent.parent / "reports"


class TestF1VerifyScriptExists:
    """F1: A verify_ghsbuilts_grid.py script must exist."""

    def test_verify_script_exists(self) -> None:
        candidates = [
            SCRIPTS_DIR / "verify_ghsbuilts_grid.py",
            SCRIPTS_DIR / "verify_ghsbuilts.py",
            SCRIPTS_DIR / "audit_ghsbuilts.py",
        ]
        assert any(c.exists() for c in candidates), (
            "No GHS-BUILT-S verify/audit script found"
        )


class TestF2VisualOutputCapability:
    """F2: Some file must produce visual output from GHS-BUILT-S data."""

    def test_plotting_references_in_ghsbuilts_scripts(self) -> None:
        plotting_keywords = {
            "matplotlib", "imshow", "savefig", "pyplot",
            "save_plot", "Figure",
        }
        ghsbuilts_keywords = {
            "ghsbuilts", "GHS_BUILT", "built_area",
        }

        matches = []
        for py_file in SCRIPTS_DIR.glob("*.py"):
            content = py_file.read_text()
            has_plot = any(kw in content for kw in plotting_keywords)
            has_ghs = any(kw in content for kw in ghsbuilts_keywords)
            if has_plot and has_ghs:
                matches.append(py_file.name)

        assert matches, (
            "No script combines GHS-BUILT-S data with plotting"
        )


class TestF3PipelineVerifyStep:
    """F3: Pipeline script must include a verify/audit step."""

    def test_pipeline_has_verify_step(self) -> None:
        pipeline = SCRIPTS_DIR / "run_ghsbuilts_pipeline.py"
        assert pipeline.exists(), "Pipeline script missing"

        content = pipeline.read_text()
        verify_indicators = [
            "verify", "audit", "plot", "visual",
            "verify_ghsbuilts", "save_plot",
        ]
        assert any(kw in content for kw in verify_indicators), (
            "Pipeline script has no verify/audit/plot step"
        )


class TestF4DataPresenceForInspection:
    """F4: Raw GeoTIFFs or compiled grid must exist on disk for inspection."""

    @pytest.mark.xfail(
        reason="no data/raw/ghsbuilts/ or data/compiled/ghsbuilts/ on disk",
        strict=True,
    )
    def test_raw_or_compiled_data_exists(self) -> None:
        project_root = Path(__file__).parent.parent
        raw = project_root / "data" / "raw" / "ghsbuilts"
        compiled = project_root / "data" / "compiled" / "ghsbuilts"

        raw_exists = raw.exists() and any(raw.iterdir())
        compiled_exists = compiled.exists() and any(
            compiled.iterdir()
        )
        assert raw_exists or compiled_exists, (
            "No GHS-BUILT-S data on disk to visually inspect"
        )


class TestF5AuditOutputParity:
    """F5: Audit output must exist at parity with other sources."""

    @pytest.mark.xfail(
        reason=(
            "no reports/audit_ghsbuilts/ — ACLED has 13 PNGs,"
            " GHS-POP has 10, GHS-BUILT-S has zero"
        ),
        strict=True,
    )
    def test_audit_pngs_exist(self) -> None:
        audit_dir = REPORTS_DIR / "audit_ghsbuilts"
        assert audit_dir.exists(), (
            "reports/audit_ghsbuilts/ directory missing"
        )
        pngs = list(audit_dir.glob("*.png"))
        assert len(pngs) >= 5, (
            f"Expected at least 5 audit PNGs, found {len(pngs)}"
        )
