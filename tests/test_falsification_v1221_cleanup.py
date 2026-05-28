"""Falsification stubs: v1.2.21 cleanup completeness audit.

Source: /falsify audit 2026-05-25
Claim: Sprint v1.2.21 cleanup is done and successfully so.
Verdict: FALSIFIED (1 hard, 2 soft).

F-1 (hard): Post-sprint register updates not done — C-164, C-176,
    C-169 remain open despite the work being complete.
F-2 (soft): README.md still describes deleted datafactory_synthetic.
F-3 (soft): 7 ARCHITECTURE.md files reference deleted module.
"""

from __future__ import annotations

import re
from pathlib import Path


class TestF1PostSprintRegisterUpdates:
    """The sprint plan's 'Register Updates After Sprint' section
    requires: update C-164 with resolved patterns, mark C-176 as
    resolved, mark C-169 as resolved, header count → 63."""

    def test_c176_marked_resolved(self) -> None:
        """C-176 (dead synthetic module) should be resolved after
        Task 9 deleted the module."""
        register = Path(
            "reports/technical_risk_register.md"
        ).read_text()
        archive = Path(
            "reports/archive/technical_risk_register_resolved.md"
        ).read_text()
        c176_lower = register.lower()
        c176_in_register = (
            "C-176" in register
            and "open" not in c176_lower.split("c-176")[0][-50:]
        )
        c176_in_archive = "C-176" in archive
        assert c176_in_register or c176_in_archive, (
            "C-176 not found in register or archive"
        )

    def test_c169_marked_resolved(self) -> None:
        """C-169 (CI signal) should be resolved after Task 2
        added skipif guards."""
        register = Path(
            "reports/technical_risk_register.md"
        ).read_text()
        archive = Path(
            "reports/archive/technical_risk_register_resolved.md"
        ).read_text()
        c169_lower = register.lower()
        c169_in_register = (
            "C-169" in register
            and "open" not in c169_lower.split("c-169")[0][-50:]
        )
        c169_in_archive = "C-169" in archive
        assert c169_in_register or c169_in_archive, (
            "C-169 not found in register or archive"
        )

    def test_c164_has_resolution_notes(self) -> None:
        """C-164 should mention resolved patterns from v1.2.21."""
        register = Path(
            "reports/technical_risk_register.md"
        ).read_text()
        c164_start = register.index("### C-164:")
        next_heading = register.index("\n### ", c164_start + 1)
        c164_text = register[c164_start:next_heading]
        assert "raster_io" in c164_text or "tagging" in c164_text, (
            "C-164 has no resolution notes for v1.2.21 — "
            "sprint plan says to update with: Pattern #2 "
            "resolved (tagging), Pattern #4 resolved (output), "
            "Pattern #5 resolved (VIEWS_EPOCH_YEAR), raster I/O "
            "resolved, temporal interpolation resolved"
        )

    def test_register_header_count(self) -> None:
        """Header open-concern count must match actual open
        entries in the summary table."""
        register = Path(
            "reports/technical_risk_register.md"
        ).read_text()
        match = re.search(
            r"(\d+) open concerns", register[:3000],
        )
        assert match, (
            "Could not find 'N open concerns' in header"
        )
        header_count = int(match.group(1))
        open_rows = [
            line for line in register.splitlines()
            if line.startswith("| C-")
            and "~~" not in line
            and "| — |" not in line.split("|")[2]
        ]
        assert header_count == len(open_rows), (
            f"Header says {header_count} open concerns "
            f"but table has {len(open_rows)} open rows"
        )


class TestF2ReadmeSyntheticReferences:
    """README.md describes the architecture including
    datafactory_synthetic, which was deleted in Task 9."""

    def test_readme_no_synthetic_reference(self) -> None:
        readme = Path("README.md").read_text()
        lines_with_ref = [
            i + 1
            for i, line in enumerate(readme.splitlines())
            if "datafactory_synthetic" in line
        ]
        assert not lines_with_ref, (
            f"README.md references deleted datafactory_synthetic "
            f"on line(s) {lines_with_ref}. The module was "
            f"deleted in v1.2.21 Task 9 but README was not "
            f"updated."
        )


class TestF3ArchitectureMdSyntheticReferences:
    """Per-package ARCHITECTURE.md files still list
    datafactory_synthetic in dependency rules."""

    def test_no_architecture_md_synthetic_refs(self) -> None:
        src = Path("src")
        arch_files = sorted(src.glob("*/ARCHITECTURE.md"))
        hits: list[str] = []
        for af in arch_files:
            text = af.read_text()
            for i, line in enumerate(text.splitlines(), 1):
                if "datafactory_synthetic" in line:
                    hits.append(f"{af}:{i}")
        assert not hits, (
            f"ARCHITECTURE.md files reference deleted "
            f"datafactory_synthetic: {hits}. These were not "
            f"included in Task 9 step 4 (only ADRs were "
            f"updated) but should be cleaned."
        )
