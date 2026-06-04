"""Operational integration: grid-producing sources must appear in refresh_pipeline.sh.

Prevents C-192 recurrence: operational integration trailing implementation.
Third occurrence caught by falsification audit (2026-05-23). This test
enforces post-mortem checklist items 9-10 automatically.
"""

from __future__ import annotations

from pathlib import Path

from datafactory_provenance.source_registry import PIPELINE_SOURCES

PROJECT_ROOT = Path(__file__).parent.parent
REFRESH_SCRIPT = PROJECT_ROOT / "scripts" / "refresh_pipeline.sh"

GRID_PRODUCING_SOURCES: dict[str, tuple[str, ...]] = {
    entry.name: entry.features
    for entry in PIPELINE_SOURCES
    if entry.features
    and entry.name not in (
        "PRIO-GRID Static",
        "PRIO-GRID Shapefile",
        "GAUL Admin",
    )
}


def _base_id(name: str) -> str:
    """Extract the base identifier from a registry name.

    "UCDP Annual" → "ucdp", "GHS-BUILT-S" → "ghsbuilts".
    """
    return name.split()[0].lower().replace("-", "")


class TestRefreshPipelineStatusPage:
    """EXIT trap must generate status page on success and failure
    (C-237)."""

    def test_exit_trap_function_exists(self) -> None:
        content = REFRESH_SCRIPT.read_text()
        assert "generate_status_on_exit()" in content, (
            "refresh_pipeline.sh must define "
            "generate_status_on_exit() function (C-237)"
        )

    def test_exit_trap_is_registered(self) -> None:
        content = REFRESH_SCRIPT.read_text()
        assert "trap generate_status_on_exit EXIT" in content, (
            "refresh_pipeline.sh must register "
            "generate_status_on_exit as EXIT trap (C-237)"
        )

    def test_status_output_path(self) -> None:
        content = REFRESH_SCRIPT.read_text()
        assert "--output data/status.html" in content, (
            "Status page must write to data/status.html "
            "(symlinked by Caddy)"
        )


class TestRefreshPipelineSourceCoverage:
    """Every grid-producing source in PIPELINE_SOURCES must be
    referenced in refresh_pipeline.sh."""

    def test_all_grid_sources_in_refresh_pipeline(self) -> None:
        content = REFRESH_SCRIPT.read_text().lower().replace("-", "")
        missing = [
            name for name in GRID_PRODUCING_SOURCES
            if _base_id(name) not in content
        ]
        assert not missing, (
            f"refresh_pipeline.sh missing steps for: {missing}. "
            f"See C-192: operational integration must not "
            f"trail implementation."
        )

    def test_deployment_guide_mentions_all_grid_sources(
        self,
    ) -> None:
        guide = (
            PROJECT_ROOT / "docs" / "guides"
            / "hetzner_deployment_guide.md"
        )
        content = guide.read_text().lower().replace("-", "")
        missing = [
            name for name in GRID_PRODUCING_SOURCES
            if _base_id(name) not in content
        ]
        assert not missing, (
            f"hetzner_deployment_guide.md missing: {missing}. "
            f"See C-192."
        )
