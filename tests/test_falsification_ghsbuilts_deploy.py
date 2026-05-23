"""Falsification stubs: GHS-BUILT-S deployment readiness.

Source: /falsify coverage parity audit 2026-05-22
Verifies source registry completeness and gitignore coverage.
"""

from __future__ import annotations

from pathlib import Path


class TestF1SourceRegistryCompleteness:
    """GHS-BUILT-S must be registered in the source registry."""

    def test_ghsbuilts_feature_in_registry(self) -> None:
        from datafactory_provenance.source_registry import (
            get_all_features,
        )

        features = get_all_features()
        assert "ghsbuilts_built_area" in features

    def test_ghsbuilts_source_entries_exist(self) -> None:
        from datafactory_provenance.source_registry import (
            PIPELINE_SOURCES,
        )

        names = [s.name for s in PIPELINE_SOURCES]
        ghsbuilts_entries = [
            n for n in names if "built-s" in n.lower()
        ]
        assert len(ghsbuilts_entries) == 3, (
            f"Expected 3 GHS-BUILT-S entries "
            f"(harvest, viewpoint, compilation), "
            f"found {len(ghsbuilts_entries)}: {ghsbuilts_entries}"
        )


class TestF2GitignoreCompleteness:
    """Raw GHS-BUILT-S data must be gitignored."""

    def test_raw_ghsbuilts_gitignored(self) -> None:
        gitignore = Path(".gitignore")
        if not gitignore.exists():
            return
        content = gitignore.read_text()
        assert "data/raw" in content or "data/" in content, (
            "Raw data directory not in .gitignore"
        )
