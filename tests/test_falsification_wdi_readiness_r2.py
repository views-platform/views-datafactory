"""Falsification round 2: WDI integration readiness (2026-06-24).

Claim: "We are ready for the WDI integration effort to start."

Soft falsification SF1: README is missing SHDI from data flow diagram,
architecture section, packages table, project structure, harvester list,
viewpoint builders, and assembly command. Test count is stale (1094 vs
actual ~1966).

Soft falsification SF2: Deployment guide lists CPX32 (8 GB RAM) but the
server was rescaled to CPX42 (16 GB + 16 GB swap) during v1.2.22.
"""

from __future__ import annotations

from pathlib import Path


class TestSF1ReadmeMentionsShdi:
    """README must mention SHDI in the data flow and architecture
    sections so a WDI developer sees the correct system state."""

    def test_readme_data_flow_mentions_shdi(self) -> None:
        readme = Path("README.md").read_text()
        data_flow_start = readme.index("### Data Flow")
        data_flow_end = readme.index("\n---", data_flow_start)
        data_flow = readme[data_flow_start:data_flow_end]

        assert "SHDI" in data_flow or "shdi" in data_flow, (
            "README data flow diagram does not mention SHDI. "
            "A WDI developer would see an incomplete picture "
            "of the system's current sources."
        )

    def test_readme_test_count_above_1900(self) -> None:
        readme = Path("README.md").read_text()
        import re

        match = re.search(r"#\s*~?(\d[\d,]*)\s*tests", readme)
        assert match, "README does not contain a test count"
        count = int(match.group(1).replace(",", ""))
        assert count >= 1900, (
            f"README says {count} tests but actual count is ~1966. "
            "Stale test count misleads contributors about suite size."
        )


class TestSF2DeployGuideServerSpec:
    """Deployment guide must reflect actual server spec."""

    def test_deploy_guide_does_not_say_cpx32(self) -> None:
        guide = Path(
            "docs/guides/hetzner_deployment_guide.md"
        ).read_text()

        quick_ref_start = guide.index("| **Type**")
        quick_ref_line = guide[
            quick_ref_start : guide.index("\n", quick_ref_start)
        ]

        assert "CPX32" not in quick_ref_line, (
            "Deployment guide quick-reference says CPX32 (8 GB) but "
            "the server was rescaled to CPX42 (16 GB + 16 GB swap). "
            "A WDI developer sizing features against the documented "
            "spec would underestimate capacity by 4x."
        )
