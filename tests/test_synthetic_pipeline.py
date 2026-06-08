"""End-to-end pipeline test with planted known-answer values.

Generates synthetic compiled grids, runs assembly → zarr export
via production scripts, then verifies exact values at each boundary.
Exercises temporal alignment, zero-fill, static broadcast, digest
gates, and consumer data loading.

Total runtime: ~10 seconds (vs 103 minutes on authentic data).
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

# scripts/ is not a package — load via importlib
_spec = importlib.util.spec_from_file_location(
    "generate_synthetic_data",
    Path(__file__).resolve().parent.parent / "scripts" / "generate_synthetic_data.py",
)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

generate = _mod.generate
ROW_A, COL_A = _mod.ROW_A, _mod.COL_A
ROW_B, COL_B = _mod.ROW_B, _mod.COL_B
PGID_A, PGID_B = _mod.PGID_A, _mod.PGID_B
UCDP_FEATURES = _mod.UCDP_FEATURES
ACLED_FEATURES = _mod.ACLED_FEATURES

pytestmark = pytest.mark.synthetic


@pytest.fixture(scope="module")
def pipeline(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """Run the full synthetic pipeline once, share across all tests."""
    root = tmp_path_factory.mktemp("synthetic")
    meta = generate(root)

    assembled = root / "assembled"
    assembled.mkdir(exist_ok=True)

    # Assembly
    result = subprocess.run(
        [
            sys.executable,
            "scripts/assemble_grid.py",
            "--ucdp-grid", str(root / "compiled"),
            "--acled-grid", str(root / "compiled" / "acled"),
            "--static-dir", str(root / "raw" / "priogrid_static"),
            "--admin-dir", str(root / "raw" / "gaul_admin"),
            "--output-dir", str(assembled),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"Assembly failed:\n{result.stdout}\n{result.stderr}"

    # Zarr export
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_zarr.py",
            "--input", str(assembled),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"Zarr export failed:\n{result.stdout}\n{result.stderr}"
    )

    return {
        "root": root,
        "assembled": assembled,
        "meta": meta,
    }


# ── Assembly: feature order ────────────────────────────────

class TestAssemblyFeatures:

    def test_feature_order(self, pipeline: dict) -> None:
        features = json.loads(
            (pipeline["assembled"] / "feature_names.json").read_text()
        )
        expected = (
            UCDP_FEATURES + ACLED_FEATURES + ["landarea", "gaul0_code"]
        )
        assert features == expected


# ── Assembly: UCDP planted values ──────────────────────────

class TestAssemblyUcdp:

    def test_cell_a_month_0(self, pipeline: dict) -> None:
        grid = np.load(pipeline["assembled"] / "grid.npy", mmap_mode="r")
        assert grid[0, ROW_A, COL_A, 0] == 7.0
        assert grid[0, ROW_A, COL_A, 1] == 3.0
        assert grid[0, ROW_A, COL_A, 2] == 1.0

    def test_cell_a_month_6(self, pipeline: dict) -> None:
        grid = np.load(pipeline["assembled"] / "grid.npy", mmap_mode="r")
        assert grid[6, ROW_A, COL_A, 0] == 11.0
        assert grid[6, ROW_A, COL_A, 1] == 5.0
        assert grid[6, ROW_A, COL_A, 2] == 2.0

    def test_cell_a_empty_month(self, pipeline: dict) -> None:
        grid = np.load(pipeline["assembled"] / "grid.npy", mmap_mode="r")
        assert grid[3, ROW_A, COL_A, 0] == 0.0

    def test_cell_b_spatial_separation(self, pipeline: dict) -> None:
        grid = np.load(pipeline["assembled"] / "grid.npy", mmap_mode="r")
        assert grid[0, ROW_B, COL_B, 0] == 99.0

    def test_unpopulated_cell_is_zero(self, pipeline: dict) -> None:
        grid = np.load(pipeline["assembled"] / "grid.npy", mmap_mode="r")
        assert grid[0, ROW_A, COL_A + 2, 0] == 0.0


# ── Assembly: ACLED temporal alignment ─────────────────────

class TestAssemblyAcledAlignment:

    def test_zero_fill_before_acled_range(self, pipeline: dict) -> None:
        grid = np.load(pipeline["assembled"] / "grid.npy", mmap_mode="r")
        acled_idx = 3  # acled_count is feature 3
        for t in range(3):
            assert grid[t, ROW_A, COL_A, acled_idx] == 0.0, (
                f"Month {t} should be zero-filled (before ACLED range)"
            )

    def test_acled_data_in_range(self, pipeline: dict) -> None:
        grid = np.load(pipeline["assembled"] / "grid.npy", mmap_mode="r")
        assert grid[3, ROW_A, COL_A, 3] == 4.0   # acled_count
        assert grid[3, ROW_A, COL_A, 4] == 8.0   # acled_fatalities
        assert grid[6, ROW_A, COL_A, 3] == 6.0
        assert grid[6, ROW_A, COL_A, 4] == 12.0

    def test_zero_fill_after_acled_range(self, pipeline: dict) -> None:
        grid = np.load(pipeline["assembled"] / "grid.npy", mmap_mode="r")
        acled_idx = 3
        for t in range(9, 12):
            assert grid[t, ROW_A, COL_A, acled_idx] == 0.0, (
                f"Month {t} should be zero-filled (after ACLED range)"
            )


# ── Assembly: static + admin ───────────────────────────────

class TestAssemblyStaticAdmin:

    def test_static_broadcast_all_months(self, pipeline: dict) -> None:
        grid = np.load(pipeline["assembled"] / "grid.npy", mmap_mode="r")
        landarea_idx = 5
        for t in range(12):
            assert grid[t, ROW_A, COL_A, landarea_idx] == 1250.0, (
                f"landarea at month {t} should be 1250.0"
            )
        assert grid[0, ROW_B, COL_B, landarea_idx] == 500.0

    def test_admin_codes(self, pipeline: dict) -> None:
        grid = np.load(pipeline["assembled"] / "grid.npy", mmap_mode="r")
        gaul_idx = 6
        assert grid[0, ROW_A, COL_A, gaul_idx] == 133.0

    def test_admin_unmatched_fill(self, pipeline: dict) -> None:
        grid = np.load(pipeline["assembled"] / "grid.npy", mmap_mode="r")
        gaul_idx = 6
        assert grid[0, ROW_A, COL_A + 2, gaul_idx] == -1.0


# ── Assembly: provenance ───────────────────────────────────

class TestAssemblyProvenance:

    def test_provenance_written(self, pipeline: dict) -> None:
        prov_path = pipeline["assembled"] / "provenance.json"
        assert prov_path.exists()
        prov = json.loads(prov_path.read_text())
        assert "output_digest" in prov


# ── Zarr export ────────────────────────────────────────────

class TestZarrExport:

    def test_zarr_ucdp_values(self, pipeline: dict) -> None:
        import zarr

        z = zarr.open(str(pipeline["assembled"] / "grid.zarr"), "r")
        assert float(z["ged_sb_best"][0, ROW_A, COL_A]) == 7.0
        assert float(z["ged_sb_best"][6, ROW_A, COL_A]) == 11.0

    def test_zarr_acled_alignment(self, pipeline: dict) -> None:
        import zarr

        z = zarr.open(str(pipeline["assembled"] / "grid.zarr"), "r")
        assert float(z["acled_count"][0, ROW_A, COL_A]) == 0.0
        assert float(z["acled_count"][3, ROW_A, COL_A]) == 4.0
        assert float(z["acled_count"][9, ROW_A, COL_A]) == 0.0

    def test_zarr_static(self, pipeline: dict) -> None:
        import zarr

        z = zarr.open(str(pipeline["assembled"] / "grid.zarr"), "r")
        assert float(z["landarea"][0, ROW_A, COL_A]) == 1250.0

    def test_zarr_source_digest(self, pipeline: dict) -> None:
        import zarr

        z = zarr.open(str(pipeline["assembled"] / "grid.zarr"), "r")
        assert "source_digest" in dict(z.attrs)

    def test_sentinel_cleared(self, pipeline: dict) -> None:
        assert not (pipeline["assembled"] / ".exports_required").exists()


# ── Consumer data loading ──────────────────────────────────

class TestConsumerLoading:

    @pytest.fixture(scope="class")
    def consumer_df(self, pipeline: dict):
        from datafactory_query.dataset import load_dataset

        return load_dataset(
            region="land",
            start=481,
            end=492,
            features=[
                "ged_sb_best", "ged_ns_best", "ged_os_best",
                "acled_count", "gaul0_code",
            ],
            output_format="dataframe",
            data_dir=pipeline["assembled"],
        )

    def test_planted_ucdp_values(self, consumer_df) -> None:
        assert consumer_df.loc[(481, PGID_A), "ged_sb_best"] == 7.0
        assert consumer_df.loc[(481, PGID_A), "ged_ns_best"] == 3.0

    def test_planted_acled_alignment(self, consumer_df) -> None:
        assert consumer_df.loc[(481, PGID_A), "acled_count"] == 0.0
        assert consumer_df.loc[(484, PGID_A), "acled_count"] == 4.0

    def test_admin_code_loaded(self, consumer_df) -> None:
        assert consumer_df.loc[(481, PGID_A), "gaul0_code"] == 133.0

    def test_spatial_separation(self, consumer_df) -> None:
        assert consumer_df.loc[(481, PGID_B), "ged_sb_best"] == 99.0
