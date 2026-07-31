"""Falsification stubs: SOLID principle compliance.

Source: /falsify audit 2026-05-27
Claim: "This project adheres to SOLID principles."
Verdict: CONTESTED (0 hard, 2 soft).

P-2 (soft): OCP violation — adding a new data source requires
    modifying assemble_grid.py and refresh_pipeline.sh. Layers 1-3
    use registries (OCP-compliant), but Layer 4+ is hardcoded.
    Accepted under WET-before-DRY (C-44, threshold: 10 sources).
P-5 (soft): SRP violation — harvester fetch_* functions mix
    HTTP I/O, file parsing, Parquet writing, and provenance
    recording in a single function (4+ reasons to change).
    Accepted under WET-before-DRY (C-44, threshold: 10 sources).
"""

from __future__ import annotations

from pathlib import Path

import pytest


class TestP2OcpAssemblyHardcoded:
    """Adding a new data source should not require modifying
    assemble_grid.py. Currently it does: the source list is
    hardcoded in argparse flags and grid-slicing logic."""

    @pytest.mark.xfail(
        reason=(
            "C-164/C-44: WET-before-DRY. Unit = pipeline sources "
            "wired into assemble_grid.py; currently 6 (UCDP, ACLED, "
            "GHS-POP, GHS-BUILT-S, V-Dem, SHDI). Threshold 10. "
            "NB the earlier reason said '9 sources', which matched "
            "no artifact in the repo — see C-164's 2026-07-31 "
            "addendum. Deferral stands; it is now countable."
        ),
        strict=True,
    )
    def test_assembly_uses_source_registry(self) -> None:
        """assemble_grid.py should discover sources from a
        registry or config, not hardcoded argument flags."""
        text = Path("scripts/assemble_grid.py").read_text()
        hardcoded_sources = [
            flag
            for flag in [
                "--ucdp-grid",
                "--acled-grid",
                "--ghspop-grid",
                "--ghsbuilts-grid",
                "--vdem-grid",
                "--shdi-grid",
            ]
            if flag in text
        ]
        assert not hardcoded_sources, (
            f"assemble_grid.py has {len(hardcoded_sources)} "
            f"hardcoded source flags: {hardcoded_sources}. "
            f"OCP says adding a source should not require "
            f"modifying existing code. Consider a source "
            f"registry or config-driven discovery."
        )

    @pytest.mark.xfail(
        reason=(
            "C-164/C-44: WET-before-DRY. Unit = compile steps in "
            "refresh_pipeline.sh; currently 6 (UCDP, ACLED, GHS-POP, "
            "GHS-BUILT-S, V-Dem, SHDI). Threshold 10. NB the earlier "
            "reason said '9 sources', which matched no artifact — "
            "see C-164's 2026-07-31 addendum."
        ),
        strict=True,
    )
    def test_pipeline_uses_source_registry(self) -> None:
        """refresh_pipeline.sh should discover compile steps
        from a config, not hardcoded step blocks."""
        text = Path("scripts/refresh_pipeline.sh").read_text()
        hardcoded_steps = [
            label
            for label in [
                "Compile UCDP",
                "Compile ACLED",
                "Compile GHS-POP",
                "Compile GHS-BUILT-S",
                "Compile V-Dem",
                "Compile SHDI",
            ]
            if label in text
        ]
        assert not hardcoded_steps, (
            f"refresh_pipeline.sh has {len(hardcoded_steps)} "
            f"hardcoded compile steps: {hardcoded_steps}."
        )


class TestP5SrpHarvesterFunctions:
    """Harvester fetch_* functions should have a single reason
    to change. Currently they mix HTTP, parsing, I/O, and
    provenance in one function."""

    @pytest.mark.xfail(
        reason=(
            "C-164/C-44: WET-before-DRY. Unit = harvester source "
            "modules under src/datafactory_harvester/sources/; "
            "currently 10 by module count, 8 by distinct upstream "
            "(UCDP is three modules, one provider). The threshold "
            "is stated in pipeline sources (6), not modules — see "
            "C-164's 2026-07-31 addendum. Extraction still deferred."
        ),
        strict=True,
    )
    def test_fetch_vdem_under_80_lines(self) -> None:
        """fetch_vdem is 159 lines because it handles download,
        extraction, parsing, writing, and provenance in one
        function."""
        import ast

        src = Path(
            "src/datafactory_harvester/sources/vdem.py"
        ).read_text()
        tree = ast.parse(src)
        for node in ast.iter_child_nodes(tree):
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == "fetch_vdem"
            ):
                end = getattr(node, "end_lineno", node.lineno)
                length = end - node.lineno + 1
                assert length <= 80, (
                    f"fetch_vdem() is {length} lines. SRP "
                    f"suggests splitting HTTP download, "
                    f"file parsing, Parquet writing, and "
                    f"provenance into separate concerns."
                )
                return
        raise AssertionError("fetch_vdem not found")
