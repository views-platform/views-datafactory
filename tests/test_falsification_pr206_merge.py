"""Falsification stubs: PR #206 merge readiness.

Source: /falsify "The PR is ready for merge" (2026-06-18)

Soft falsifications:
  F2 — Risk register header breakdown stale (43 struck → 52 actual)
  F6a — C-230 resolved but not struck through in WET-before-DRY work package
  F6b — C-254 resolved but not struck through in Artifact consistency work package
"""

from __future__ import annotations

import re
from pathlib import Path

REGISTER = Path("reports/technical_risk_register.md")


class TestF2HeaderBreakdownAccuracy:
    """Header breakdown counts must match actual file contents."""

    def test_struck_through_count_matches_header(self) -> None:
        text = REGISTER.read_text()

        header_match = re.search(
            r"(\d+) struck-through in active register", text,
        )
        assert header_match, "No struck-through count in header"
        header_count = int(header_match.group(1))

        actual = len(re.findall(r"^\| ~~C-\d+~~", text, re.MULTILINE))
        assert header_count == actual, (
            f"Header says '{header_count} struck-through' "
            f"but found {actual} struck-through C-entries"
        )

    def test_full_entry_count_matches_header(self) -> None:
        text = REGISTER.read_text()

        header_match = re.search(
            r"(\d+) resolved concerns as full entries", text,
        )
        assert header_match, "No full-entry count in header"
        header_count = int(header_match.group(1))

        archive = Path(
            "reports/archive/technical_risk_register_resolved.md",
        )
        actual = len(
            re.findall(r"^### C-\d+", archive.read_text(), re.MULTILINE),
        )
        assert header_count == actual, (
            f"Header says '{header_count} full entries' "
            f"but archive has {actual}"
        )


class TestF6WorkPackageStaleness:
    """Resolved entries must be struck through in work packages."""

    def test_c230_struck_in_work_packages(self) -> None:
        text = REGISTER.read_text()
        wp_match = re.search(
            r"## Work Packages.*?(?=\n## )", text, re.DOTALL,
        )
        assert wp_match, "Work packages section not found"
        wp = wp_match.group()

        for line in wp.split("\n"):
            if "WET-before-DRY" in line:
                assert "~~C-230~~" in line or "C-230" not in line, (
                    "C-230 resolved but not struck through in "
                    "WET-before-DRY work package"
                )
                break

    def test_c254_struck_in_work_packages(self) -> None:
        text = REGISTER.read_text()
        wp_match = re.search(
            r"## Work Packages.*?(?=\n## )", text, re.DOTALL,
        )
        assert wp_match
        wp = wp_match.group()

        for line in wp.split("\n"):
            if "Artifact consistency" in line:
                assert "~~C-254~~" in line or "C-254" not in line, (
                    "C-254 resolved but not struck through in "
                    "Artifact consistency work package"
                )
                break
