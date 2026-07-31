"""Falsification stubs: GHS-BUILT-S implementation completeness.

Source: /falsify audit 2026-05-23
Claim: "The GHS-BUILT-S data is successfully and correctly implemented.
        This effort is done."

Hard and soft falsifications from the audit. Each stub encodes a gap
that must be addressed before the claim can be reasserted.
"""

from __future__ import annotations

import re
from pathlib import Path

DOCS_DIR = Path(__file__).parent.parent / "docs"
REPORTS_DIR = Path(__file__).parent.parent / "reports"
PROJECT_ROOT = Path(__file__).parent.parent


class TestS1CicParity:
    """P5-soft: GHS-BUILT-S config classes lack CIC files."""

    def test_ghsbuilts_config_has_cic(self) -> None:
        cic = DOCS_DIR / "CICs" / "GhsBuiltSConfig.md"
        assert cic.exists(), (
            "GhsBuiltSConfig has no CIC — ACLED has AcledConfig.md,"
            " GHS-POP has GhsPopConfig.md"
        )

    def test_ghsbuilts_viewpoint_config_has_cic(self) -> None:
        cic = DOCS_DIR / "CICs" / "GhsBuiltSViewpointConfig.md"
        assert cic.exists(), (
            "GhsBuiltSViewpointConfig has no CIC —"
            " GHS-POP has GhsPopViewpointConfig.md"
        )


class TestS2ClaudeMdArchitecture:
    """P5-soft: the architecture doc omits GHS-BUILT-S.

    Retargeted from CLAUDE.md to README.md 2026-07-31 —
    CLAUDE.md is now untracked, and README is the published
    architecture description, so drift there matters more.
    """

    def test_assembly_description_includes_ghsbuilts(self) -> None:
        arch_doc = PROJECT_ROOT / "README.md"
        content = arch_doc.read_text()
        assert "GHS-BUILT-S" in content, (
            "README.md Assembly description lists UCDP + ACLED +"
            " GHS-POP but omits GHS-BUILT-S"
        )


class TestH1RegisterHeaderArithmetic:
    """P7-hard: risk register header tier counts must match table."""

    def test_tier_counts_match_summary_table(self) -> None:
        register = REPORTS_DIR / "technical_risk_register.md"
        content = register.read_text()
        lines = content.split("\n")

        header_match = re.search(
            r"(\d+) Tier 2, (\d+) Tier 3, (\d+) Tier 4",
            content,
        )
        assert header_match, "Cannot parse tier counts from header"
        claimed_t2 = int(header_match.group(1))
        claimed_t3 = int(header_match.group(2))
        claimed_t4 = int(header_match.group(3))

        in_table = False
        actual = {2: 0, 3: 0, 4: 0}
        for line in lines:
            if "| ID | Tier |" in line:
                in_table = True
                continue
            if in_table and line.startswith("|"):
                if "|-" in line:
                    continue
                cols = [c.strip() for c in line.split("|")]
                if len(cols) < 4:
                    continue
                id_col = cols[1]
                tier_col = cols[2]
                if "~~" in id_col:
                    continue
                if not re.search(r"C-\d+", id_col):
                    continue
                tier_match = re.search(r"(\d)", tier_col)
                if tier_match:
                    t = int(tier_match.group(1))
                    if t in actual:
                        actual[t] += 1
            elif in_table and not line.startswith("|"):
                break

        assert actual[2] == claimed_t2, (
            f"Tier 2: table has {actual[2]},"
            f" header claims {claimed_t2}"
        )
        assert actual[3] == claimed_t3, (
            f"Tier 3: table has {actual[3]},"
            f" header claims {claimed_t3}"
        )
        assert actual[4] == claimed_t4, (
            f"Tier 4: table has {actual[4]},"
            f" header claims {claimed_t4}"
        )
