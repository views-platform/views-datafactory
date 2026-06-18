"""Characterization tests for pipeline runner scripts (C-164, Pattern #8 prep).

These tests verify the CLI interface of each pipeline runner script
without executing actual pipeline steps.  They exist so that PR-5
(PipelineRunner extraction) can verify that refactoring preserves
behavior.
"""

from __future__ import annotations

import importlib.util
import inspect
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"

PIPELINE_SCRIPTS: list[str] = [
    "run_acled_pipeline",
    "run_ghspop_pipeline",
    "run_ghsbuilts_pipeline",
    "run_vdem_pipeline",
    "run_shdi_pipeline",
]


def _load_script(name: str) -> ModuleType:
    """Load a pipeline script by file path (scripts/ is not a package)."""
    path = SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_help(script: str) -> subprocess.CompletedProcess[str]:
    """Run a pipeline script with --help and return the result."""
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / f"{script}.py"), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )


# ── Module structure ─────────────────────────────────────────────────


class TestModuleStructure:
    """Every pipeline script must be importable and expose main()."""

    @pytest.mark.parametrize("script", PIPELINE_SCRIPTS)
    def test_script_file_exists(self, script: str) -> None:
        path = SCRIPTS_DIR / f"{script}.py"
        assert path.exists(), f"{path} not found"

    @pytest.mark.parametrize("script", PIPELINE_SCRIPTS)
    def test_importable(self, script: str) -> None:
        mod = _load_script(script)
        assert mod is not None

    @pytest.mark.parametrize("script", PIPELINE_SCRIPTS)
    def test_has_main_function(self, script: str) -> None:
        mod = _load_script(script)
        assert hasattr(mod, "main"), f"{script} missing main()"
        assert callable(mod.main)

    @pytest.mark.parametrize("script", PIPELINE_SCRIPTS)
    def test_has_steps_tuple(self, script: str) -> None:
        mod = _load_script(script)
        assert hasattr(mod, "STEPS"), f"{script} missing STEPS"
        assert isinstance(mod.STEPS, tuple)
        assert len(mod.STEPS) >= 2


# ── --help exits 0 ───────────────────────────────────────────────────


class TestHelpFlag:
    """--help must exit 0 and print usage for every script."""

    @pytest.mark.parametrize("script", PIPELINE_SCRIPTS)
    def test_help_exits_zero(self, script: str) -> None:
        result = _run_help(script)
        assert result.returncode == 0, (
            f"{script} --help failed: {result.stderr}"
        )
        assert "usage:" in result.stdout.lower()


# ── --force flag accepted ────────────────────────────────────────────


class TestForceFlag:
    """--force must be accepted (appears in help output)."""

    @pytest.mark.parametrize("script", PIPELINE_SCRIPTS)
    def test_force_in_help(self, script: str) -> None:
        result = _run_help(script)
        assert "--force" in result.stdout, (
            f"{script} --help does not mention --force"
        )


# ── --skip-to flag accepted ─────────────────────────────────────────


class TestSkipToFlag:
    """--skip-to must be accepted with correct choices."""

    @pytest.mark.parametrize("script", PIPELINE_SCRIPTS)
    def test_skip_to_in_help(self, script: str) -> None:
        result = _run_help(script)
        assert "--skip-to" in result.stdout, (
            f"{script} --help does not mention --skip-to"
        )

    def test_acled_skip_to_choices(self) -> None:
        result = _run_help("run_acled_pipeline")
        for choice in ("consolidate", "viewpoint", "compile"):
            assert choice in result.stdout, (
                f"ACLED pipeline missing --skip-to choice: {choice}"
            )

    def test_ghspop_skip_to_choices(self) -> None:
        result = _run_help("run_ghspop_pipeline")
        for choice in ("viewpoint", "compile"):
            assert choice in result.stdout, (
                f"GHS-POP pipeline missing --skip-to choice: {choice}"
            )

    def test_ghsbuilts_skip_to_choices(self) -> None:
        result = _run_help("run_ghsbuilts_pipeline")
        for choice in ("viewpoint", "compile"):
            assert choice in result.stdout, (
                f"GHS-BUILT-S pipeline missing --skip-to choice: {choice}"
            )

    def test_vdem_skip_to_choices(self) -> None:
        result = _run_help("run_vdem_pipeline")
        for choice in ("viewpoint", "compile"):
            assert choice in result.stdout, (
                f"V-Dem pipeline missing --skip-to choice: {choice}"
            )


# ── Invalid arguments rejected ───────────────────────────────────────


class TestInvalidArgs:
    """Unknown flags must cause non-zero exit."""

    @pytest.mark.parametrize("script", PIPELINE_SCRIPTS)
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

    @pytest.mark.parametrize("script", PIPELINE_SCRIPTS)
    def test_invalid_skip_to_rejected(self, script: str) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / f"{script}.py"),
                "--skip-to", "nonexistent_step",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0


# ── Source-specific argument presence ────────────────────────────────


class TestSourceSpecificArgs:
    """Verify source-specific CLI flags exist in help output."""

    def test_acled_has_start_year(self) -> None:
        result = _run_help("run_acled_pipeline")
        assert "--start-year" in result.stdout

    def test_acled_has_end_year(self) -> None:
        result = _run_help("run_acled_pipeline")
        assert "--end-year" in result.stdout

    def test_ghspop_has_epochs(self) -> None:
        result = _run_help("run_ghspop_pipeline")
        assert "--epochs" in result.stdout

    def test_ghspop_has_end_year(self) -> None:
        result = _run_help("run_ghspop_pipeline")
        assert "--end-year" in result.stdout

    def test_ghsbuilts_has_epochs(self) -> None:
        result = _run_help("run_ghsbuilts_pipeline")
        assert "--epochs" in result.stdout

    def test_ghsbuilts_has_end_year(self) -> None:
        result = _run_help("run_ghsbuilts_pipeline")
        assert "--end-year" in result.stdout

    def test_ghsbuilts_has_verify(self) -> None:
        result = _run_help("run_ghsbuilts_pipeline")
        assert "--verify" in result.stdout

    def test_vdem_has_end_year(self) -> None:
        result = _run_help("run_vdem_pipeline")
        assert "--end-year" in result.stdout

    def test_vdem_has_verify(self) -> None:
        result = _run_help("run_vdem_pipeline")
        assert "--verify" in result.stdout


# ── STEPS tuple content ──────────────────────────────────────────────


class TestStepsTupleContent:
    """Verify STEPS tuple has expected values per pipeline."""

    def test_acled_steps(self) -> None:
        mod = _load_script("run_acled_pipeline")
        assert mod.STEPS == (
            "harvest", "consolidate", "viewpoint", "compile"
        )

    def test_ghspop_steps(self) -> None:
        mod = _load_script("run_ghspop_pipeline")
        assert mod.STEPS == ("harvest", "viewpoint", "compile")

    def test_ghsbuilts_steps(self) -> None:
        mod = _load_script("run_ghsbuilts_pipeline")
        assert mod.STEPS == ("harvest", "viewpoint", "compile")

    def test_vdem_steps(self) -> None:
        mod = _load_script("run_vdem_pipeline")
        assert mod.STEPS == ("harvest", "viewpoint", "compile")


# ── Cross-cutting conventions ────────────────────────────────────────


class TestPipelineConventions:
    """Cross-cutting conventions shared by all pipeline scripts."""

    @pytest.mark.parametrize("script", PIPELINE_SCRIPTS)
    def test_has_shebang(self, script: str) -> None:
        path = SCRIPTS_DIR / f"{script}.py"
        first_line = path.read_text().split("\n")[0]
        assert first_line.startswith("#!/"), (
            f"{script} missing shebang line"
        )

    @pytest.mark.parametrize("script", PIPELINE_SCRIPTS)
    def test_has_docstring(self, script: str) -> None:
        mod = _load_script(script)
        assert mod.__doc__ is not None, f"{script} missing module docstring"

    @pytest.mark.parametrize("script", PIPELINE_SCRIPTS)
    def test_has_ifmain_guard(self, script: str) -> None:
        path = SCRIPTS_DIR / f"{script}.py"
        source = path.read_text()
        assert 'if __name__ == "__main__"' in source, (
            f"{script} missing if __name__ guard"
        )

    @pytest.mark.parametrize("script", PIPELINE_SCRIPTS)
    def test_main_returns_int(self, script: str) -> None:
        mod = _load_script(script)
        sig = inspect.signature(mod.main)
        ann = sig.return_annotation
        assert ann is int or ann == "int", (
            f"{script}.main() return annotation is {ann}, expected int"
        )

    @pytest.mark.parametrize("script", PIPELINE_SCRIPTS)
    def test_steps_first_is_harvest(self, script: str) -> None:
        mod = _load_script(script)
        assert mod.STEPS[0] == "harvest", (
            f"{script} STEPS should start with 'harvest'"
        )

    @pytest.mark.parametrize("script", PIPELINE_SCRIPTS)
    def test_steps_last_is_compile(self, script: str) -> None:
        mod = _load_script(script)
        assert mod.STEPS[-1] == "compile", (
            f"{script} STEPS should end with 'compile'"
        )


# ── Characterization: pipeline CLI contracts (C-230, #202) ─────────────


class TestPipelineStepsContent:
    """STEPS tuple must have meaningful content."""

    @pytest.mark.parametrize("script", PIPELINE_SCRIPTS)
    def test_steps_are_nonempty(self, script: str) -> None:
        mod = _load_script(script)
        assert len(mod.STEPS) >= 2, (
            f"{script}.STEPS has {len(mod.STEPS)} entries, need >= 2"
        )


class TestPipelineCompleteness:
    """Test list must match the actual scripts/ glob."""

    def test_all_pipeline_scripts_covered(self) -> None:
        on_disk = sorted(
            p.stem for p in SCRIPTS_DIR.glob("run_*_pipeline.py")
        )
        assert on_disk == sorted(PIPELINE_SCRIPTS), (
            f"Test list mismatch — on disk: {on_disk}, "
            f"in tests: {sorted(PIPELINE_SCRIPTS)}"
        )
