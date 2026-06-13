"""Falsification tests: documentation consistency and coverage.

Claim: governance documentation is internally consistent and covers
the responsibility-boundary domain completely.

Audit date: 2026-06-13
Probes: P-1 (interpolation principle), P-3 (CLAUDE.md drift),
        P-5 (ADR index), P-6 (temporal.py contract), P-7 (cross-source rule)
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ADRS = REPO / "docs" / "ADRs"
CLAUDE_MD = REPO / "CLAUDE.md"
REFRESH = REPO / "scripts" / "refresh_pipeline.sh"


class TestClaudeMdSourceCompleteness:
    """P-3: CLAUDE.md must list every source in the assembled grid."""

    def test_assembly_layer_lists_shdi(self):
        text = CLAUDE_MD.read_text()
        assembly_match = re.search(
            r"Assembly.*?combines.*?→.*?assembled",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        assert assembly_match is not None, (
            "Could not find Assembly layer description in CLAUDE.md"
        )
        assembly_line = assembly_match.group(0).lower()
        assert "shdi" in assembly_line, (
            "CLAUDE.md Assembly layer description does not mention SHDI. "
            "refresh_pipeline.sh passes --shdi-grid to assemble_grid.py "
            "but CLAUDE.md still lists only 7 sources."
        )

    def test_harvester_sources_list_shdi(self):
        text = CLAUDE_MD.read_text()
        harvester_match = re.search(
            r"datafactory_harvester.*?pluggable sources:(.*?)(?:\n-|\Z)",
            text,
            re.DOTALL,
        )
        assert harvester_match is not None, (
            "Could not find harvester package description in CLAUDE.md"
        )
        harvester_line = harvester_match.group(1).lower()
        assert "shdi" in harvester_line, (
            "CLAUDE.md harvester package description does not mention SHDI "
            "as a pluggable source."
        )


class TestAdrIndexCompleteness:
    """P-5: ADR README must list every ADR file that exists."""

    def test_all_adr_files_in_readme(self):
        readme = (ADRS / "README.md").read_text()
        adr_files = sorted(
            f.stem
            for f in ADRS.glob("0*.md")
        )
        missing = []
        for stem in adr_files:
            adr_num = stem.split("_")[0]
            if adr_num not in readme:
                missing.append(stem)
        assert not missing, (
            f"ADR files exist but are not listed in README.md: {missing}"
        )


class TestTemporalModuleContract:
    """P-6: shared temporal interpolation module should have its
    contract documented in a constitutional ADR or standalone doc,
    not just inside source-specific ADRs."""

    def test_temporal_policy_in_constitutional_adr(self):
        adr014 = ADRS / "014_viewpoints_as_derived_views.md"
        assert adr014.exists(), "ADR-014 not found"
        text = adr014.read_text().lower()
        assert "temporal interpolation" in text, (
            "ADR-014 (constitutional viewpoint ADR) does not mention "
            "temporal interpolation. The shared temporal.py module's "
            "contract should be governed by the constitutional ADR, "
            "not scattered across source-specific ADRs."
        )
        full_text = adr014.read_text()
        has_ref = (
            "datafactory_viewpoint.temporal" in full_text
            or "temporal.py" in full_text
        )
        assert has_ref, (
            "ADR-014 discusses temporal interpolation but does not "
            "reference the shared implementation module."
        )


class TestCrossSourcePrincipleIsFormalized:
    """P-7: 'no cross-source dependencies' should be stated as a
    formal principle in a constitutional ADR, not just referenced
    reactively in source-specific ADRs."""

    def test_cross_source_rule_in_constitutional_adr(self):
        constitutional = [
            ADRS / "001_ontology_of_the_repository.md",
            ADRS / "012_four_layer_data_architecture.md",
            ADRS / "014_viewpoints_as_derived_views.md",
        ]
        found = False
        for adr in constitutional:
            if not adr.exists():
                continue
            text = adr.read_text().lower()
            if "cross-source" in text or "cross source" in text:
                found = True
                break
        assert found, (
            "'No cross-source dependencies' is a foundational constraint "
            "referenced in ADR-029 and ADR-042 but is NOT stated in any "
            "constitutional ADR (001, 012, 014). The principle is implicit "
            "in ADR-014's 'pure function' clause but never named."
        )


class TestInterpolationPrincipleDocumented:
    """P-1: there should be a documented general principle for when
    temporal interpolation is permitted vs forbidden, not just
    per-source ad hoc decisions."""

    def test_ghs_builts_adr_states_interpolation_rationale(self):
        candidates = list(ADRS.glob("034_*"))
        assert candidates, "ADR-034 not found"
        adr034 = candidates[0]
        text = adr034.read_text().lower()
        has_rationale = any(
            phrase in text
            for phrase in [
                "interpolation is appropriate",
                "interpolation is justified",
                "why interpolat",
                "rationale for interpolat",
                "interpolation because",
            ]
        )
        assert has_rationale, (
            "ADR-034 (GHS-BUILT-S) permits temporal interpolation but "
            "provides no rationale for WHY it is appropriate for built-up "
            "surface area. It inherits GHS-POP's approach ('same 12 epochs') "
            "without justifying the analogy. Compare: ADR-029 (GHS-POP) "
            "and ADR-042 (SHDI) both provide explicit rationales."
        )
