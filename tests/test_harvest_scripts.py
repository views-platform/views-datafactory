"""Characterization tests for harvest scripts (C-230, Pattern #8 prep).

These tests verify the CLI interface of each harvest script without
making network calls.  They exist so that HarvestRunner extraction
can verify that refactoring preserves behavior.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load_script(name: str) -> ModuleType:
    """Load a harvest script by file path (scripts/ is not a package)."""
    path = SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

HARVEST_SCRIPTS: list[str] = [
    "harvest_ucdp",
    "harvest_acled",
    "harvest_ghspop",
    "harvest_ghsbuilts",
    "harvest_priogrid",
    "harvest_gaul",
    "harvest_vdem",
    "harvest_shdi",
    "harvest_shapefile",
]


def _run_help(script: str) -> subprocess.CompletedProcess[str]:
    """Run a harvest script with --help and return the result."""
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / f"{script}.py"), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )


# ── Module structure ─────────────────────────────────────────────────


class TestModuleStructure:
    """Every harvest script must be importable and expose main()."""

    @pytest.mark.parametrize("script", HARVEST_SCRIPTS)
    def test_script_file_exists(self, script: str) -> None:
        path = SCRIPTS_DIR / f"{script}.py"
        assert path.exists(), f"{path} not found"

    @pytest.mark.parametrize("script", HARVEST_SCRIPTS)
    def test_importable(self, script: str) -> None:
        mod = _load_script(script)
        assert mod is not None

    @pytest.mark.parametrize("script", HARVEST_SCRIPTS)
    def test_has_main_function(self, script: str) -> None:
        mod = _load_script(script)
        assert hasattr(mod, "main"), f"{script} missing main()"
        assert callable(mod.main)


# ── --help exits 0 ───────────────────────────────────────────────────


class TestHelpFlag:
    """--help must exit 0 and print usage for every script."""

    @pytest.mark.parametrize("script", HARVEST_SCRIPTS)
    def test_help_exits_zero(self, script: str) -> None:
        result = _run_help(script)
        assert result.returncode == 0, (
            f"{script} --help failed: {result.stderr}"
        )
        assert "usage:" in result.stdout.lower()


# ── --force flag accepted ────────────────────────────────────────────


class TestForceFlag:
    """--force must be accepted (appears in help output)."""

    @pytest.mark.parametrize("script", HARVEST_SCRIPTS)
    def test_force_in_help(self, script: str) -> None:
        result = _run_help(script)
        assert "--force" in result.stdout, (
            f"{script} --help does not mention --force"
        )


# ── Invalid arguments rejected ───────────────────────────────────────


class TestInvalidArgs:
    """Unknown flags must cause non-zero exit."""

    @pytest.mark.parametrize("script", HARVEST_SCRIPTS)
    def test_unknown_flag_rejected(self, script: str) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / f"{script}.py"),
                "--this-flag-does-not-exist",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0


# ── Source-specific argument presence ────────────────────────────────


class TestSourceSpecificArgs:
    """Verify source-specific CLI flags exist in help output."""

    def test_ucdp_has_source_flag(self) -> None:
        result = _run_help("harvest_ucdp")
        assert "--source" in result.stdout

    def test_acled_has_start_year(self) -> None:
        result = _run_help("harvest_acled")
        assert "--start-year" in result.stdout

    def test_acled_has_end_year(self) -> None:
        result = _run_help("harvest_acled")
        assert "--end-year" in result.stdout

    def test_acled_has_proof(self) -> None:
        result = _run_help("harvest_acled")
        assert "--proof" in result.stdout

    def test_ghspop_has_epochs(self) -> None:
        result = _run_help("harvest_ghspop")
        assert "--epochs" in result.stdout

    def test_ghsbuilts_has_epochs(self) -> None:
        result = _run_help("harvest_ghsbuilts")
        assert "--epochs" in result.stdout

    def test_priogrid_has_variables(self) -> None:
        result = _run_help("harvest_priogrid")
        assert "--variables" in result.stdout

    def test_gaul_has_variables(self) -> None:
        result = _run_help("harvest_gaul")
        assert "--variables" in result.stdout


# ── Characterization: CLI contracts (C-230, #201) ──────────────────────

_SOURCE_KEYWORDS: dict[str, str] = {
    "harvest_ucdp": "ucdp",
    "harvest_acled": "acled",
    "harvest_ghspop": "ghspop",
    "harvest_ghsbuilts": "ghsbuilts",
    "harvest_priogrid": "priogrid",
    "harvest_gaul": "gaul",
    "harvest_vdem": "vdem",
    "harvest_shdi": "shdi",
    "harvest_shapefile": "shapefile",
}


class TestHarvestBanner:
    """--help output must mention the source and work without network."""

    @pytest.mark.parametrize("script", HARVEST_SCRIPTS)
    def test_help_output_contains_source_name(
        self, script: str,
    ) -> None:
        result = _run_help(script)
        keyword = _SOURCE_KEYWORDS[script]
        assert keyword in result.stdout.lower(), (
            f"{script} --help does not mention '{keyword}'"
        )

    @pytest.mark.parametrize("script", HARVEST_SCRIPTS)
    def test_help_no_network_required(self, script: str) -> None:
        result = _run_help(script)
        assert result.returncode == 0, (
            f"{script} --help failed (rc={result.returncode})"
        )


class TestHarvestCompleteness:
    """Test list must match the actual scripts/ glob."""

    def test_all_harvest_scripts_covered(self) -> None:
        on_disk = sorted(
            p.stem for p in SCRIPTS_DIR.glob("harvest_*.py")
        )
        assert on_disk == sorted(HARVEST_SCRIPTS), (
            f"Test list mismatch — on disk: {on_disk}, "
            f"in tests: {sorted(HARVEST_SCRIPTS)}"
        )
