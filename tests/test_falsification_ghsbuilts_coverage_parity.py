"""Falsification stubs: GHS-BUILT-S test coverage parity.

Source: /falsify audit 2026-05-22
Claim: "GHS-BUILT-S has a full visual audit with at least as much coverage
        and depth as the three other data sources combined."

All 5 probes falsified the claim. These stubs encode the parity thresholds
that must be met before the claim can be reasserted.
"""

from __future__ import annotations

from pathlib import Path

TESTS_DIR = Path(__file__).parent

GHSBUILTS_FILES = [
    "test_ghsbuilts_harvester.py",
    "test_ghsbuilts_viewpoint.py",
    "test_ghsbuilts_compilation.py",
]

OTHER_SOURCE_FILES = [
    "test_acled_harvester.py",
    "test_acled_viewpoint.py",
    "test_acled_compilation.py",
    "test_acled_consolidation.py",
    "test_falsification_acled_phase2.py",
    "test_ghspop_harvester.py",
    "test_ghspop_viewpoint.py",
    "test_ghspop_compilation.py",
    "test_falsification_ghspop_deploy.py",
    "test_falsification_ghspop_deploy_v2.py",
    "test_falsification_ghspop_deploy_v3.py",
    "test_falsification_ghspop_memory.py",
    "test_priogrid_static.py",
    "test_gaul_admin.py",
    "test_falsification_priogrid_static.py",
    "test_falsification_priogrid_reaudit.py",
]


def _count_pattern(files: list[str], pattern: str) -> int:
    total = 0
    for f in files:
        path = TESTS_DIR / f
        if path.exists():
            total += path.read_text().count(pattern)
    return total


def _count_lines(files: list[str]) -> int:
    total = 0
    for f in files:
        path = TESTS_DIR / f
        if path.exists():
            total += len(path.read_text().splitlines())
    return total


class TestF1TestFunctionParity:
    """F1: GHS-BUILT-S test function count >= 70% of combined others."""

    def test_test_function_count_parity(self) -> None:
        ours = _count_pattern(GHSBUILTS_FILES, "def test_")
        theirs = _count_pattern(OTHER_SOURCE_FILES, "def test_")
        threshold = int(theirs * 0.7)
        assert ours >= threshold, (
            f"GHS-BUILT-S has {ours} test functions vs {theirs} "
            f"for other sources combined ({ours/theirs:.0%}), "
            f"need {threshold} for 70%"
        )


class TestF2AssertionDensityParity:
    """F2: GHS-BUILT-S assertion count >= 70% of combined others."""

    def test_assertion_count_parity(self) -> None:
        ours = _count_pattern(GHSBUILTS_FILES, "assert")
        theirs = _count_pattern(OTHER_SOURCE_FILES, "assert")
        threshold = int(theirs * 0.7)
        assert ours >= threshold, (
            f"GHS-BUILT-S has {ours} assertions vs {theirs} "
            f"for other sources combined ({ours/theirs:.0%}), "
            f"need {threshold} for 70%"
        )


class TestF3RedTeamClassParity:
    """F3: GHS-BUILT-S Red-team class count >= 70% of combined others."""

    def test_red_class_count_parity(self) -> None:
        our_red = sum(
            1
            for f in GHSBUILTS_FILES
            for line in (TESTS_DIR / f).read_text().splitlines()
            if line.strip().startswith("class Test") and "Red" in line
        )
        their_red = sum(
            1
            for f in OTHER_SOURCE_FILES
            if (TESTS_DIR / f).exists()
            for line in (TESTS_DIR / f).read_text().splitlines()
            if line.strip().startswith("class Test") and "Red" in line
        )
        threshold = int(their_red * 0.7)
        assert our_red >= threshold, (
            f"GHS-BUILT-S has {our_red} Red classes vs {their_red} "
            f"for other sources combined, need {threshold} for 70%"
        )


class TestF4FalsificationFileParity:
    """F4: GHS-BUILT-S has dedicated falsification test files."""

    def test_falsification_file_exists(self) -> None:
        ours = list(TESTS_DIR.glob("test_falsification_ghsbuilts*.py"))
        theirs = (
            list(TESTS_DIR.glob("test_falsification_acled*.py"))
            + list(TESTS_DIR.glob("test_falsification_ghspop*.py"))
            + list(TESTS_DIR.glob("test_falsification_priogrid*.py"))
        )
        assert len(ours) >= len(theirs), (
            f"GHS-BUILT-S has {len(ours)} falsification files vs "
            f"{len(theirs)} for other sources combined"
        )


class TestF5ViewpointTestDepthParity:
    """F5: GHS-BUILT-S viewpoint test lines >= GHS-POP viewpoint alone."""

    def test_viewpoint_line_parity(self) -> None:
        ours = _count_lines(["test_ghsbuilts_viewpoint.py"])
        ghspop = _count_lines(["test_ghspop_viewpoint.py"])
        assert ours >= ghspop, (
            f"GHS-BUILT-S viewpoint tests: {ours} lines vs "
            f"GHS-POP viewpoint alone: {ghspop} lines"
        )
