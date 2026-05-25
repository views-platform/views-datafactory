"""Falsification stubs: documentation is up to date (2026-05-25).

Hard falsifications:
  F1 — 7 of 8 ARCHITECTURE.md files have stale module lists
  F3 — docs/sources/README.md references 4 catalog cards that don't exist

Soft falsification:
  F2 — docs/CICs/README.md lists 21 active contracts but 28 exist
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


# --- F1: ARCHITECTURE.md files must list all modules in their package ---


class TestF1ArchitectureMdCompleteness:
    """Each ARCHITECTURE.md must mention every .py file in its package."""

    def test_compilation_architecture_lists_output_py(self) -> None:
        arch = (ROOT / "src/datafactory_compilation/ARCHITECTURE.md").read_text()
        assert "output.py" in arch, (
            "datafactory_compilation/ARCHITECTURE.md does not mention output.py "
            "(extracted in v1.2.21)"
        )

    def test_compilation_architecture_lists_pregridded(self) -> None:
        arch = (ROOT / "src/datafactory_compilation/ARCHITECTURE.md").read_text()
        assert "pregridded_compilation.py" in arch, (
            "datafactory_compilation/ARCHITECTURE.md does not mention "
            "pregridded_compilation.py"
        )

    def test_compilation_architecture_no_synthetic(self) -> None:
        arch = (ROOT / "src/datafactory_compilation/ARCHITECTURE.md").read_text()
        assert "synthetic" not in arch.lower(), (
            "datafactory_compilation/ARCHITECTURE.md still references deleted "
            "datafactory_synthetic module"
        )

    def test_viewpoint_architecture_lists_raster_io(self) -> None:
        arch = (ROOT / "src/datafactory_viewpoint/ARCHITECTURE.md").read_text()
        assert "raster_io.py" in arch, (
            "datafactory_viewpoint/ARCHITECTURE.md does not mention raster_io.py "
            "(extracted in v1.2.21)"
        )

    def test_viewpoint_architecture_lists_temporal(self) -> None:
        arch = (ROOT / "src/datafactory_viewpoint/ARCHITECTURE.md").read_text()
        assert "temporal.py" in arch, (
            "datafactory_viewpoint/ARCHITECTURE.md does not mention temporal.py "
            "(extracted in v1.2.21)"
        )

    def test_viewpoint_architecture_lists_all_builders(self) -> None:
        arch = (ROOT / "src/datafactory_viewpoint/ARCHITECTURE.md").read_text()
        for builder in ("ghspop_v1.py", "ghsbuilts_v1.py", "acled_v1.py"):
            assert builder in arch, (
                f"datafactory_viewpoint/ARCHITECTURE.md does not mention {builder}"
            )

    def test_consolidation_architecture_lists_tagging(self) -> None:
        arch = (ROOT / "src/datafactory_consolidation/ARCHITECTURE.md").read_text()
        assert "tagging.py" in arch, (
            "datafactory_consolidation/ARCHITECTURE.md does not mention tagging.py "
            "(extracted in v1.2.21)"
        )

    def test_consolidation_architecture_lists_acled(self) -> None:
        arch = (ROOT / "src/datafactory_consolidation/ARCHITECTURE.md").read_text()
        assert "acled.py" in arch, (
            "datafactory_consolidation/ARCHITECTURE.md does not mention "
            "consolidators/acled.py"
        )

    def test_harvester_architecture_lists_all_sources(self) -> None:
        arch = (ROOT / "src/datafactory_harvester/ARCHITECTURE.md").read_text()
        for source in ("acled.py", "ghspop.py", "ghsbuilts.py", "gaul_admin.py"):
            assert source in arch, (
                f"datafactory_harvester/ARCHITECTURE.md does not mention {source}"
            )


# --- F3: Source catalog cards must exist for every row in the index ---


class TestF3SourceCatalogCompleteness:
    """Every source listed in docs/sources/README.md must have a .md file."""

    @pytest.mark.parametrize(
        "card",
        ["ucdp.md", "acled.md", "priogrid_static.md", "gaul_admin.md"],
    )
    def test_catalog_card_exists(self, card: str) -> None:
        path = ROOT / "docs" / "sources" / card
        assert path.exists(), (
            f"docs/sources/README.md references {card} but the file does not exist"
        )


# --- F2: CIC README must list all active CIC files ---


class TestF2CicRegistryCompleteness:
    """docs/CICs/README.md must list every .md file in docs/CICs/."""

    def test_cic_readme_lists_all_cics(self) -> None:
        readme = (ROOT / "docs/CICs/README.md").read_text()
        cic_dir = ROOT / "docs" / "CICs"
        cic_files = {
            f.stem
            for f in cic_dir.glob("*.md")
            if f.name not in ("README.md", "cic_template.md")
        }
        missing = [name for name in cic_files if name not in readme]
        assert not missing, (
            f"docs/CICs/README.md is missing {len(missing)} CIC entries: "
            f"{sorted(missing)}"
        )
