"""Content-addressed skip: prove that unchanged inputs skip assembly + export.

Uses synthetic data to demonstrate:
1. First run: full pipeline, all values correct
2. Second run (unchanged): both assembly and export skip, values still correct
3. Third run (ACLED modified): assembly + export run, new values correct

This is the correctness proof for the pipeline speedup. If the skip
logic has a bug (stale data served, changed data not rebuilt), these
tests catch it with known-answer values.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

_spec = importlib.util.spec_from_file_location(
    "generate_synthetic_data",
    Path(__file__).resolve().parent.parent / "scripts" / "generate_synthetic_data.py",
)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

generate = _mod.generate
ROW_A, COL_A = _mod.ROW_A, _mod.COL_A
ROW_B, COL_B = _mod.ROW_B, _mod.COL_B

pytestmark = pytest.mark.synthetic


def _run_assembly(root: Path, *, skip: bool = False) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable,
        "scripts/assemble_grid.py",
        "--ucdp-grid", str(root / "compiled"),
        "--acled-grid", str(root / "compiled" / "acled"),
        "--static-dir", str(root / "raw" / "priogrid_static"),
        "--admin-dir", str(root / "raw" / "gaul_admin"),
        "--output-dir", str(root / "assembled"),
    ]
    if skip:
        cmd.append("--skip-if-unchanged")
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


def _run_export(root: Path, *, skip: bool = False) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable,
        "scripts/export_zarr.py",
        "--input", str(root / "assembled"),
    ]
    if skip:
        cmd.append("--skip-if-unchanged")
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


class TestFullPipelineThenSkip:
    """Run full pipeline, then run again with skip — values preserved."""

    @pytest.fixture(scope="class")
    def root(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        return tmp_path_factory.mktemp("skip_test")

    @pytest.fixture(scope="class")
    def first_run(self, root: Path) -> dict:
        generate(root)
        (root / "assembled").mkdir(exist_ok=True)

        t0 = time.monotonic()
        r = _run_assembly(root)
        assert r.returncode == 0, f"Assembly failed:\n{r.stdout}\n{r.stderr}"

        r = _run_export(root)
        assert r.returncode == 0, f"Export failed:\n{r.stdout}\n{r.stderr}"
        elapsed = time.monotonic() - t0

        return {"elapsed": elapsed, "root": root}

    @pytest.fixture(scope="class")
    def second_run(self, first_run: dict) -> dict:
        root = first_run["root"]

        t0 = time.monotonic()
        r = _run_assembly(root, skip=True)
        assert r.returncode == 0, f"Assembly skip failed:\n{r.stdout}\n{r.stderr}"
        assembly_skipped = "SKIP:" in r.stdout

        r = _run_export(root, skip=True)
        assert r.returncode == 0, f"Export skip failed:\n{r.stdout}\n{r.stderr}"
        export_skipped = "SKIP:" in r.stdout
        elapsed = time.monotonic() - t0

        return {
            "elapsed": elapsed,
            "assembly_skipped": assembly_skipped,
            "export_skipped": export_skipped,
            "root": root,
        }

    def test_first_run_values_correct(self, first_run: dict) -> None:
        grid = np.load(first_run["root"] / "assembled" / "grid.npy", mmap_mode="r")
        assert grid[0, ROW_A, COL_A, 0] == 7.0
        assert grid[3, ROW_A, COL_A, 3] == 4.0
        assert grid[0, ROW_B, COL_B, 0] == 99.0

    def test_assembly_skipped(self, second_run: dict) -> None:
        assert second_run["assembly_skipped"], (
            "Assembly should skip when inputs unchanged"
        )

    def test_export_skipped(self, second_run: dict) -> None:
        assert second_run["export_skipped"], (
            "Export should skip when assembly unchanged"
        )

    def test_skip_is_faster(self, first_run: dict, second_run: dict) -> None:
        assert second_run["elapsed"] < first_run["elapsed"] * 0.5, (
            f"Skip run ({second_run['elapsed']:.1f}s) should be "
            f"much faster than full run ({first_run['elapsed']:.1f}s)"
        )

    def test_values_preserved_after_skip(self, second_run: dict) -> None:
        grid = np.load(second_run["root"] / "assembled" / "grid.npy", mmap_mode="r")
        assert grid[0, ROW_A, COL_A, 0] == 7.0
        assert grid[3, ROW_A, COL_A, 3] == 4.0
        assert grid[0, ROW_B, COL_B, 0] == 99.0

    def test_zarr_preserved_after_skip(self, second_run: dict) -> None:
        import zarr

        z = zarr.open(str(second_run["root"] / "assembled" / "grid.zarr"), "r")
        assert float(z["ged_sb_best"][0, ROW_A, COL_A]) == 7.0
        assert float(z["acled_count"][3, ROW_A, COL_A]) == 4.0


class TestModifiedInputRebuilds:
    """Modify ACLED source, run with skip — should rebuild with new values."""

    @pytest.fixture(scope="class")
    def root(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        return tmp_path_factory.mktemp("rebuild_test")

    @pytest.fixture(scope="class")
    def after_modify(self, root: Path) -> dict:
        generate(root)
        (root / "assembled").mkdir(exist_ok=True)

        # First run: full pipeline
        r = _run_assembly(root)
        assert r.returncode == 0, f"Assembly 1 failed:\n{r.stdout}\n{r.stderr}"
        r = _run_export(root)
        assert r.returncode == 0, f"Export 1 failed:\n{r.stdout}\n{r.stderr}"

        # Verify original ACLED value
        grid = np.load(root / "assembled" / "grid.npy", mmap_mode="r")
        assert grid[3, ROW_A, COL_A, 3] == 4.0

        # Modify ACLED source: change acled_count from 4.0 to 99.0
        acled_grid = np.load(root / "compiled" / "acled" / "grid.npy")
        acled_grid[0, ROW_A, COL_A, 0] = 99.0
        np.save(root / "compiled" / "acled" / "grid.npy", acled_grid)

        # Second run with skip: should detect change and rebuild
        r = _run_assembly(root, skip=True)
        assert r.returncode == 0, f"Assembly 2 failed:\n{r.stdout}\n{r.stderr}"
        assembly_skipped = "SKIP:" in r.stdout
        assembly_rebuilt = "Input changed" in r.stdout

        r = _run_export(root, skip=True)
        assert r.returncode == 0, f"Export 2 failed:\n{r.stdout}\n{r.stderr}"
        export_skipped = "SKIP:" in r.stdout

        return {
            "root": root,
            "assembly_skipped": assembly_skipped,
            "assembly_rebuilt": assembly_rebuilt,
            "export_skipped": export_skipped,
        }

    def test_assembly_not_skipped(self, after_modify: dict) -> None:
        assert not after_modify["assembly_skipped"], (
            "Assembly should NOT skip when ACLED input changed"
        )

    def test_assembly_detected_change(self, after_modify: dict) -> None:
        assert after_modify["assembly_rebuilt"], (
            "Assembly should report which input changed"
        )

    def test_export_not_skipped(self, after_modify: dict) -> None:
        assert not after_modify["export_skipped"], (
            "Export should NOT skip when assembly produced new grid"
        )

    def test_new_acled_value_in_grid(self, after_modify: dict) -> None:
        grid = np.load(
            after_modify["root"] / "assembled" / "grid.npy", mmap_mode="r",
        )
        assert grid[3, ROW_A, COL_A, 3] == 99.0, (
            "Modified ACLED value should appear in rebuilt grid"
        )

    def test_ucdp_value_unchanged(self, after_modify: dict) -> None:
        grid = np.load(
            after_modify["root"] / "assembled" / "grid.npy", mmap_mode="r",
        )
        assert grid[0, ROW_A, COL_A, 0] == 7.0, (
            "UCDP value should be unchanged after ACLED modification"
        )

    def test_zarr_has_new_value(self, after_modify: dict) -> None:
        import zarr

        z = zarr.open(
            str(after_modify["root"] / "assembled" / "grid.zarr"), "r",
        )
        assert float(z["acled_count"][3, ROW_A, COL_A]) == 99.0
        assert float(z["ged_sb_best"][0, ROW_A, COL_A]) == 7.0


class TestSkipCorrectness:
    """Verify skip logic handles C-259, C-260, C-261, C-262 correctly."""

    @pytest.fixture(scope="class")
    def root(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        return tmp_path_factory.mktemp("correctness_test")

    @pytest.fixture(scope="class")
    def baseline(self, root: Path) -> dict:
        """Run full pipeline once to establish provenance baseline."""
        generate(root)
        (root / "assembled").mkdir(exist_ok=True)
        r = _run_assembly(root)
        assert r.returncode == 0, f"Baseline assembly failed:\n{r.stdout}\n{r.stderr}"
        r = _run_export(root)
        assert r.returncode == 0, f"Baseline export failed:\n{r.stdout}\n{r.stderr}"
        return {"root": root}

    def test_static_change_triggers_rebuild(self, baseline: dict) -> None:
        """C-259: changing a static Parquet file must prevent skip."""
        root = baseline["root"]
        import pandas as pd

        static_path = root / "raw" / "priogrid_static" / "landarea.parquet"
        df = pd.read_parquet(static_path)
        df["value"] = df["value"] + 1.0
        df.to_parquet(static_path, index=False)

        r = _run_assembly(root, skip=True)
        assert r.returncode == 0, f"Assembly failed:\n{r.stdout}\n{r.stderr}"
        assert "SKIP:" not in r.stdout, (
            "Assembly should NOT skip when static input changed"
        )

    def test_admin_change_triggers_rebuild(self, baseline: dict) -> None:
        """C-259: changing an admin Parquet file must prevent skip."""
        root = baseline["root"]
        import pandas as pd

        admin_path = root / "raw" / "gaul_admin" / "gaul0_code.parquet"
        df = pd.read_parquet(admin_path)
        df["value"] = df["value"] + 1
        df.to_parquet(admin_path, index=False)

        r = _run_assembly(root, skip=True)
        assert r.returncode == 0, f"Assembly failed:\n{r.stdout}\n{r.stderr}"
        assert "SKIP:" not in r.stdout, (
            "Assembly should NOT skip when admin input changed"
        )

    def test_admin_digest_in_provenance(self, baseline: dict) -> None:
        """Provenance must record admin_digest when admin dir is provided."""
        import json

        prov_path = baseline["root"] / "assembled" / "provenance.json"
        prov = json.loads(prov_path.read_text())
        admin_digest = prov["sources"].get("admin_digest")
        assert admin_digest is not None, (
            "provenance.json must contain a non-None admin_digest "
            "when admin parquets are provided"
        )

    def test_force_flag_bypasses_skip(self, baseline: dict) -> None:
        """C-261: --force must prevent skip even when inputs unchanged."""
        root = baseline["root"]
        cmd = [
            sys.executable,
            "scripts/assemble_grid.py",
            "--ucdp-grid", str(root / "compiled"),
            "--acled-grid", str(root / "compiled" / "acled"),
            "--static-dir", str(root / "raw" / "priogrid_static"),
            "--admin-dir", str(root / "raw" / "gaul_admin"),
            "--output-dir", str(root / "assembled"),
            "--skip-if-unchanged",
            "--force",
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, f"Assembly failed:\n{r.stdout}\n{r.stderr}"
        assert "SKIP:" not in r.stdout, (
            "Assembly should NOT skip when --force is set"
        )

    def test_skip_records_ledger_entry(self, baseline: dict) -> None:
        """C-261: a skip must write an 'unchanged' ledger entry."""
        root = baseline["root"]

        r = _run_assembly(root, skip=True)
        assert r.returncode == 0, f"Assembly failed:\n{r.stdout}\n{r.stderr}"
        assert "SKIP:" in r.stdout, "Expected skip on unchanged inputs"

        import json as _json

        ledger_path = root / "assembled" / "ledger.jsonl"
        assert ledger_path.exists(), "Ledger file should exist after skip"
        entries = [
            _json.loads(line)
            for line in ledger_path.read_text().strip().split("\n")
        ]
        unchanged = [e for e in entries if e.get("outcome") == "unchanged"]
        assert len(unchanged) >= 1, (
            "Ledger should contain at least one 'unchanged' entry"
        )

    def test_corrupt_output_triggers_rebuild(self, baseline: dict) -> None:
        """C-262: truncated grid.npy must prevent skip."""
        root = baseline["root"]
        grid_path = root / "assembled" / "grid.npy"
        grid_path.write_bytes(b"CORRUPT")

        r = _run_assembly(root, skip=True)
        assert r.returncode == 0, f"Assembly failed:\n{r.stdout}\n{r.stderr}"
        assert "SKIP:" not in r.stdout, (
            "Assembly should NOT skip when output is corrupt"
        )

    def test_export_force_bypasses_skip(self, baseline: dict) -> None:
        """C-261: --force on export must prevent skip."""
        root = baseline["root"]
        cmd = [
            sys.executable,
            "scripts/export_zarr.py",
            "--input", str(root / "assembled"),
            "--skip-if-unchanged",
            "--force",
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, f"Export failed:\n{r.stdout}\n{r.stderr}"
        assert "SKIP:" not in r.stdout, (
            "Export should NOT skip when --force is set"
        )

    def test_export_skip_records_ledger_entry(self, baseline: dict) -> None:
        """C-261: export skip must write an 'unchanged' ledger entry."""
        root = baseline["root"]

        r = _run_export(root, skip=True)
        assert r.returncode == 0, f"Export failed:\n{r.stdout}\n{r.stderr}"
        assert "SKIP:" in r.stdout, "Expected export skip on unchanged grid"

        import json as _json

        ledger_path = root / "assembled" / "export_ledger.jsonl"
        assert ledger_path.exists(), "Export ledger file should exist after skip"
        entries = [
            _json.loads(line)
            for line in ledger_path.read_text().strip().split("\n")
        ]
        unchanged = [e for e in entries if e.get("outcome") == "unchanged"]
        assert len(unchanged) >= 1, (
            "Export ledger should contain at least one 'unchanged' entry"
        )
