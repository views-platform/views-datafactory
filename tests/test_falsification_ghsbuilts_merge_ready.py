"""Falsification stubs: GHS-BUILT-S merge readiness.

Source: /falsify audit 2026-05-23
Claim: "The GHS-BUILT-S data is successfully and correctly implemented.
        This effort is done and we can merge to development."

Hard and soft falsifications from the audit. Each stub encodes a gap
that must be addressed before the claim can be reasserted.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"


class TestH1RefreshPipelineMissingGhsBuiltS:
    """P1-hard: refresh_pipeline.sh has no GHS-BUILT-S steps."""

    def test_refresh_pipeline_harvests_ghsbuilts(self) -> None:
        script = PROJECT_ROOT / "scripts" / "refresh_pipeline.sh"
        content = script.read_text()
        assert "harvest_ghsbuilts" in content or "run_ghsbuilts" in content, (
            "refresh_pipeline.sh has no GHS-BUILT-S harvest step —"
            " GHS-POP has harvest_ghspop.py on line 133"
        )

    def test_refresh_pipeline_compiles_ghsbuilts(self) -> None:
        script = PROJECT_ROOT / "scripts" / "refresh_pipeline.sh"
        content = script.read_text()
        assert "ghsbuilts" in content.lower(), (
            "refresh_pipeline.sh has no GHS-BUILT-S compile step —"
            " GHS-POP has run_ghspop_pipeline.py on line 163"
        )

    def test_refresh_pipeline_assembles_with_ghsbuilts(self) -> None:
        script = PROJECT_ROOT / "scripts" / "refresh_pipeline.sh"
        content = script.read_text()
        assert "--ghsbuilts-grid" in content, (
            "refresh_pipeline.sh assembly step missing --ghsbuilts-grid flag —"
            " --ghspop-grid is on line 171"
        )


class TestS1DeploymentGuideMissingGhsBuiltS:
    """P2-soft: Deployment guide has no GHS-BUILT-S paragraph."""

    def test_deployment_guide_mentions_ghsbuilts(self) -> None:
        guide = DOCS_DIR / "guides" / "hetzner_deployment_guide.md"
        content = guide.read_text()
        assert "GHS-BUILT-S" in content, (
            "hetzner_deployment_guide.md has no GHS-BUILT-S paragraph —"
            " GHS-POP has one at lines 163-169"
        )


class TestS2RefreshPipelineHeaderStale:
    """P4-soft: refresh_pipeline.sh header comments omit GHS-BUILT-S."""

    def test_header_lists_ghsbuilts_in_harvest(self) -> None:
        script = PROJECT_ROOT / "scripts" / "refresh_pipeline.sh"
        lines = script.read_text().split("\n")
        header = "\n".join(lines[:20])
        assert "GHS-BUILT-S" in header, (
            "refresh_pipeline.sh header lists sources without GHS-BUILT-S —"
            " line 9 says 'UCDP, PRIO-GRID, GAUL, ACLED, GHS-POP'"
        )
