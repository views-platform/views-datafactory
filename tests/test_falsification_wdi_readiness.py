"""Falsification: WDI integration readiness (2026-06-24).

Claim: "We are ready for the WDI integration effort to start."

Soft falsification SF1: integration guide layer path table is missing
V-Dem and SHDI — a developer following the guide for a tabular non-event
source (like WDI) would not find their pattern type.

Soft falsification SF2: pre-WDI test hardening issues (#235-#240) are
OPEN on GitHub despite all underlying work being completed and merged.
The WDI roadmap's prerequisites section is also stale (3 of 5 resolved
but not updated).
"""

from __future__ import annotations

from pathlib import Path


class TestSF1IntegrationGuideLayerPaths:
    """The integration guide's layer path table must include all
    current integration patterns, including tabular non-event sources."""

    def test_guide_mentions_vdem_or_shdi_path(self) -> None:
        guide = Path(
            "docs/guides/data_source_integration_guide.md"
        ).read_text()

        before_phase_0 = guide[: guide.index("## Phase 0")]
        layer_table = before_phase_0[
            before_phase_0.rindex("| Path") :
        ]

        assert "V-Dem" in layer_table or "SHDI" in layer_table, (
            "Layer path table is missing V-Dem and SHDI. "
            "A developer integrating a tabular non-event source "
            "(like WDI) would not find their pattern type."
        )

    def test_guide_intro_source_count_current(self) -> None:
        guide = Path(
            "docs/guides/data_source_integration_guide.md"
        ).read_text()

        intro = guide[: guide.index("## Phase 0")]
        assert "four source" not in intro.lower(), (
            "Guide intro says 'four source integrations' but "
            "the codebase now has 8+. Stale intro misleads about "
            "the guide's coverage."
        )


class TestSF2PreWdiTrackingIssuesClosed:
    """Pre-WDI test hardening issues should be closed when
    their underlying work is merged."""

    def test_pre_wdi_hardening_issues_closed(self) -> None:
        import json
        import subprocess

        result = subprocess.run(
            [
                "gh", "issue", "list",
                "--search", "Pre-WDI Test Hardening in:title",
                "--state", "open",
                "--json", "number,title",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return

        open_issues = json.loads(result.stdout)
        tracking = [
            i for i in open_issues
            if "pre-wdi" in i["title"].lower()
            or i["number"] in (235, 236, 237, 238, 239, 240)
        ]
        assert len(tracking) == 0, (
            f"{len(tracking)} pre-WDI tracking issues still open "
            "despite underlying work being merged: "
            + ", ".join(
                f"#{i['number']} ({i['title']})"
                for i in tracking
            )
        )
