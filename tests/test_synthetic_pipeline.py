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

    # ── #501: the export's phase breakdown ─────────────────

    @staticmethod
    def _export_entry(pipeline: dict) -> dict:
        """The successful export entry from the run's own ledger."""
        ledger = pipeline["assembled"] / "export_ledger.jsonl"
        assert ledger.exists(), "export wrote no ledger"
        entries = [
            json.loads(line)
            for line in ledger.read_text().splitlines()
            if line.strip()
        ]
        successes = [
            e for e in entries
            if e.get("stage") == "export" and e.get("outcome") == "success"
        ]
        assert successes, f"no successful export entry in {entries}"
        return successes[-1]

    def test_phase_timings_recorded(self, pipeline: dict) -> None:
        """Every phase #501 asks about reaches the ledger, by name.

        The export took 5h07m on 2026-10-16 with no breakdown, so the
        cost could not be attributed. If a phase label is dropped here,
        that blindness returns silently — hence an exact-set assertion
        rather than a subset one.

        ``other`` is in the set as of 2026-10-21 (#514), and it is the
        member most worth asserting. The four named phases were already
        persisted; ``other`` was printed to the log and dropped, so the
        production entry for the 17,773.8s export accounted for
        17,017.2s. A reader had to sum four numbers and subtract to
        discover 756.6s was missing. Logs rotate monthly keeping 12 and
        the ledger does not, so the durable copy was the lossy one —
        which inverts the reason the ledger carries timings at all.

        Exact-set still, and for a second reason now: ``other`` is a
        residual, so a *new* phase added to the dict after it would be
        counted twice. An exact set makes that addition fail here, where
        the fix is obvious, rather than only in
        ``test_phases_account_for_the_total``, where the symptom is an
        arithmetic mismatch.
        """
        entry = self._export_entry(pipeline)
        assert "phase_seconds" in entry, entry
        assert set(entry["phase_seconds"]) == {
            "scan", "write", "verify", "swap", "other"
        }, entry["phase_seconds"]

    def test_phase_timings_are_nonnegative(self, pipeline: dict) -> None:
        phases = self._export_entry(pipeline)["phase_seconds"]
        assert all(v >= 0 for v in phases.values()), phases

    def test_phases_account_for_the_total(self, pipeline: dict) -> None:
        """The phases must account for the whole reported total.

        Was ``test_phases_do_not_exceed_the_total``, a one-sided
        ``sum <= elapsed + 0.5``. That form was right while ``other``
        sat outside ``phase_seconds`` and the phases genuinely need not
        have summed to the total. Since #514 ``other`` is the residual
        *inside* the dict, so the sum should equal the total and the
        one-sided check would pass on an entry that silently lost a
        phase. Two-sided is now the honest assertion, and the rename
        says what it checks.

        The tolerance is derived, not picked, and the derivation is why
        the ledger stores two decimals. Every value goes through
        ``round(v, 2)``: five phases contribute at most 0.005s of
        rounding each and ``elapsed_seconds`` another 0.005s, so the
        worst-case disagreement is 0.03s. 0.05 leaves headroom.

        At the previous ``round(v, 1)`` that bound was **0.30s**, and the
        synthetic export this fixture runs takes **0.4s end to end** — so
        the tolerance exceeded the entire runtime and this assertion
        passed on every wrong value it was handed. Measured, not
        suspected: with ``other`` forced to ``0.0`` the sum was 0.2s
        against an elapsed of 0.4s, a 0.2s gap, comfortably inside 0.5.
        A guard that cannot fail on the only fixture that runs it is
        decoration, which is what the drill in #514 exposed.

        What this still catches, which is why it is not a tautology
        despite ``other`` being defined as the residual: a phase
        recorded *after* the residual is computed. That addition would
        be double-counted and push the sum past the total. A negative
        residual — a timer spanning work it does not own, the original
        worry #501 had — is caught by the nonnegativity test next door.
        """
        entry = self._export_entry(pipeline)
        elapsed = entry["elapsed_seconds"]
        assert elapsed > 0, entry
        total = sum(entry["phase_seconds"].values())
        assert abs(total - elapsed) <= 0.05, (
            f"phases sum to {total}s but total is {elapsed}s "
            f"(worst case from rounding is 0.03s): "
            f"{entry['phase_seconds']}"
        )


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
