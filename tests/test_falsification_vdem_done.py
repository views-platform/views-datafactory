"""Falsification stubs: V-Dem integration completeness.

Source: /falsify we are done with the vdem integration (2026-05-26)
Claim: V-Dem integration is complete.
Verdict: FALSIFIED (3 hard, 1 soft).

F-1 (hard): No CICs for VdemConfig or VdemViewpointConfig — integration
    guide Phase 5 requires them in the same commit as Phase 2-4.
F-2 (hard): ADR-033 source catalog table missing V-Dem row.
F-3 (hard): docs/sources/README.md missing V-Dem row, feature count 53 not 75.
    docs/ADRs/README.md missing ADR-035 entry.
F-4 (soft): Compilation tests have 5 functions vs 16-18 for peers — already
    tracked in C-203.
"""

from __future__ import annotations

from pathlib import Path

DOCS = Path("docs")


class TestF1CicCompleteness:
    """Integration guide Phase 5 requires CICs for config dataclasses."""

    def test_vdem_config_cic_exists(self) -> None:
        cic = DOCS / "CICs" / "VdemConfig.md"
        assert cic.exists(), (
            "docs/CICs/VdemConfig.md does not exist — "
            "integration guide Phase 5 line 129 requires "
            "'CIC for config dataclass(es)' in same commit. "
            "GHS-POP and GHS-BUILT-S both have config CICs."
        )

    def test_vdem_viewpoint_config_cic_exists(self) -> None:
        cic = DOCS / "CICs" / "VdemViewpointConfig.md"
        assert cic.exists(), (
            "docs/CICs/VdemViewpointConfig.md does not exist — "
            "integration guide Phase 5 line 129 requires "
            "'CIC for config dataclass(es)' in same commit. "
            "GHS-POP and GHS-BUILT-S both have viewpoint CICs."
        )


class TestF2Adr033SourceTable:
    """ADR-033 illustrative source table should list all current sources."""

    def test_adr033_illustrative_table_has_vdem(self) -> None:
        adr = DOCS / "ADRs" / "033_data_source_catalog.md"
        text = adr.read_text()
        index_section = text.split("### Index file")[1].split("## ")[0]
        assert "V-Dem" in index_section, (
            "ADR-033 illustrative source table (Index file "
            "section) does not list V-Dem — the table example "
            "is stale (also missing GHS-BUILT-S)."
        )


class TestF3DocumentationIndices:
    """Index files must include V-Dem entries."""

    def test_sources_readme_lists_vdem(self) -> None:
        readme = (DOCS / "sources" / "README.md").read_text()
        assert "vdem" in readme.lower(), (
            "docs/sources/README.md does not list V-Dem — "
            "the catalog card exists (vdem.md) but the "
            "index table was not updated."
        )

    def test_sources_readme_feature_count_79(self) -> None:
        readme = (DOCS / "sources" / "README.md").read_text()
        assert "79" in readme.split("Total features")[1], (
            "docs/sources/README.md total feature count is not "
            "79 — should be 79 after SHDI (4 features added). "
        )

    def test_adrs_readme_lists_035(self) -> None:
        readme = (DOCS / "ADRs" / "README.md").read_text()
        assert "035" in readme, (
            "docs/ADRs/README.md does not list ADR-035 — "
            "the ADR exists but the index was not updated."
        )


class TestF4AdrDrift:
    """ADR-009 and ADR-016 must reflect current codebase."""

    def test_adr009_grid_shape_4d(self) -> None:
        adr_path = (
            DOCS / "ADRs"
            / "009_boundary_contracts_and_configuration_validation.md"
        )
        adr = adr_path.read_text()
        assert "n_steps" in adr and "nrow" in adr and "ncol" in adr, (
            "ADR-009 compiled output contract does not reference "
            "4D grid shape (n_steps, nrow, ncol, n_features)"
        )

    def test_adr016_documents_per_source_registries(self) -> None:
        adr = (DOCS / "ADRs" / "016_viewpoint_profiles.md").read_text()
        assert "ACLED_PROFILES" in adr or "per-source" in adr.lower(), (
            "ADR-016 does not document the per-source "
            "registry pattern (PROFILES vs ACLED_PROFILES)"
        )


class TestF5ConsumerGuide:
    """Consumer data guide must reflect 79 features."""

    def test_consumer_guide_says_79(self) -> None:
        guide = (DOCS / "guides" / "consumer_data_guide.md").read_text()
        inventory = guide.split("Feature inventory")[1].split("##")[0]
        assert "51" not in inventory, (
            "consumer_data_guide.md feature inventory still says 51"
        )
        assert "79" in guide, (
            "consumer_data_guide.md does not mention 79 features"
        )

    def test_consumer_guide_lists_vdem(self) -> None:
        guide = (DOCS / "guides" / "consumer_data_guide.md").read_text()
        assert "V-Dem" in guide or "vdem" in guide.lower(), (
            "consumer_data_guide.md does not mention V-Dem"
        )
