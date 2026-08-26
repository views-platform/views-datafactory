"""Characterization: consumer parquet provenance (C-254, #199).

Pin the provenance manifest behavior of generate_consumer_data.py.
Source script is NOT modified.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import unittest.mock
from pathlib import Path

import numpy as np
import pandas as pd

from datafactory_provenance import compute_file_digest

SCRIPT = Path(__file__).parent.parent / "scripts" / "generate_consumer_data.py"

_spec = importlib.util.spec_from_file_location(
    "generate_consumer_data", SCRIPT,
)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["generate_consumer_data"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]


def _fake_partition(
    run_type: str,
    start: int,
    end: int,
    **kwargs: object,
) -> pd.DataFrame:
    n_months = end - start + 1
    n_cells = 4
    idx = pd.MultiIndex.from_product(
        [range(start, end + 1), range(1, n_cells + 1)],
        names=["month_id", "priogrid_id"],
    )
    return pd.DataFrame(
        {
            "ged_sb_best": np.zeros(n_months * n_cells),
            "ged_ns_best": np.zeros(n_months * n_cells),
            "ged_os_best": np.zeros(n_months * n_cells),
            "gaul0_code": np.ones(n_months * n_cells),
        },
        index=idx,
    )


def _make_synthetic_grid(data_dir: Path) -> Path:
    grid = np.zeros((12, 360, 720, 4), dtype=np.float32)
    grid_path = data_dir / "grid.npy"
    np.save(grid_path, grid)
    np.save(data_dir / "pgids.npy", np.arange(1, 259201))
    np.save(data_dir / "time_steps.npy", np.arange(12))
    names = ["ged_sb_best", "ged_ns_best", "ged_os_best", "gaul0_code"]
    (data_dir / "feature_names.json").write_text(json.dumps(names))
    return grid_path


def _run_main(
    data_dir: Path, output_dir: Path,
) -> int:
    # The cooperating-child env var keeps the in-process main() from
    # acquiring the REAL /var/lock/views-pipeline.lock: hold_pipeline_lock
    # holds for process lifetime, so without this the pytest process
    # itself becomes the lock holder and every later test that spawns a
    # writer subprocess is refused (C-319 — 42 suite errors, v1.8.1).
    with (
        unittest.mock.patch.dict(
            os.environ, {"VIEWS_PIPELINE_LOCK_HELD": "1"},
        ),
        unittest.mock.patch.object(
            _mod, "generate_partition", side_effect=_fake_partition,
        ),
        unittest.mock.patch(
            "sys.argv",
            [
                "generate_consumer_data.py",
                "--data-dir", str(data_dir),
                "--output-dir", str(output_dir),
                "--partition", "calibration",
            ],
        ),
    ):
        return _mod.main()


class TestConsumerProvenance:
    """Pin provenance manifest behavior."""

    def test_provenance_json_written(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "assembled"
        data_dir.mkdir()
        _make_synthetic_grid(data_dir)
        out = tmp_path / "consumer"
        out.mkdir()

        rc = _run_main(data_dir, out)
        assert rc == 0
        assert (out / "provenance.json").exists()

    def test_provenance_schema(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "assembled"
        data_dir.mkdir()
        _make_synthetic_grid(data_dir)
        out = tmp_path / "consumer"
        out.mkdir()

        _run_main(data_dir, out)
        manifest = json.loads((out / "provenance.json").read_text())

        required = {
            "generation_timestamp",
            "source_grid_digest",
            "features",
            "output_files",
        }
        assert required <= set(manifest.keys()), (
            f"Missing keys: {required - set(manifest.keys())}"
        )

    def test_source_digest_matches_input(
        self, tmp_path: Path,
    ) -> None:
        data_dir = tmp_path / "assembled"
        data_dir.mkdir()
        grid_path = _make_synthetic_grid(data_dir)
        out = tmp_path / "consumer"
        out.mkdir()

        _run_main(data_dir, out)
        manifest = json.loads((out / "provenance.json").read_text())
        expected = compute_file_digest(grid_path)
        assert manifest["source_grid_digest"] == expected

    def test_output_digests_match_files(
        self, tmp_path: Path,
    ) -> None:
        data_dir = tmp_path / "assembled"
        data_dir.mkdir()
        _make_synthetic_grid(data_dir)
        out = tmp_path / "consumer"
        out.mkdir()

        _run_main(data_dir, out)
        manifest = json.loads((out / "provenance.json").read_text())

        for path_str, digest in manifest["output_files"].items():
            pq_path = Path(path_str)
            assert pq_path.exists(), f"{path_str} not found"
            assert compute_file_digest(pq_path) == digest

    def test_digest_mismatch_returns_nonzero(
        self, tmp_path: Path,
    ) -> None:
        data_dir = tmp_path / "assembled"
        data_dir.mkdir()
        _make_synthetic_grid(data_dir)

        prov = {"output_digest": "0000000000000000"}
        (data_dir / "provenance.json").write_text(
            json.dumps(prov),
        )

        out = tmp_path / "consumer"
        out.mkdir()
        rc = _run_main(data_dir, out)
        assert rc == 1, (
            "Script should abort (rc=1) when grid digest "
            "does not match assembly provenance"
        )


class TestConsumerManifestCarriesCoverageBounds:
    """FAO and CRAF'd consume the parquet, not the zarr.

    The zarr publishes coverage bounds in its attributes; the consumer
    manifest carried digests and filenames and no bounds at all, so a
    parquet consumer had no way to tell a zero-filled month for an
    unreported source from a month the source observed as zero (#476).
    The bounds are already in assembly provenance — the manifest just
    never copied them.
    """

    def _assembled_with_bounds(self, data_dir: Path) -> None:
        _make_synthetic_grid(data_dir)
        (data_dir / "provenance.json").write_text(json.dumps({
            "last_valid_month_id": 560,
            "first_valid_acled_month_id": 481,
            "last_valid_acled_month_id": 559,
            "first_valid_vdem_month_id": 109,
            "last_valid_vdem_month_id": 547,
        }))

    def test_manifest_carries_both_coverage_maps(
        self, tmp_path: Path,
    ) -> None:
        data_dir = tmp_path / "assembled"
        data_dir.mkdir()
        self._assembled_with_bounds(data_dir)
        out = tmp_path / "consumer"
        out.mkdir()

        _run_main(data_dir, out)
        manifest = json.loads((out / "provenance.json").read_text())

        assert manifest["first_valid_month_ids"] == {
            "first_valid_acled_month_id": 481,
            "first_valid_vdem_month_id": 109,
        }
        assert manifest["last_valid_month_ids"] == {
            "last_valid_acled_month_id": 559,
            "last_valid_vdem_month_id": 547,
        }

    def test_singular_ucdp_bound_is_carried_under_its_own_name(
        self, tmp_path: Path,
    ) -> None:
        """Same compatibility rule as the zarr: consumers read
        `last_valid_month_id` by that exact name (C-352)."""
        data_dir = tmp_path / "assembled"
        data_dir.mkdir()
        self._assembled_with_bounds(data_dir)
        out = tmp_path / "consumer"
        out.mkdir()

        _run_main(data_dir, out)
        manifest = json.loads((out / "provenance.json").read_text())

        assert manifest["last_valid_month_id"] == 560
        assert (
            "last_valid_month_id" not in manifest["last_valid_month_ids"]
        )

    def test_absent_bounds_leave_the_manifest_unchanged(
        self, tmp_path: Path,
    ) -> None:
        """Assembly provenance without bounds must not add empty keys —
        an empty map reads as 'no source has coverage'."""
        data_dir = tmp_path / "assembled"
        data_dir.mkdir()
        _make_synthetic_grid(data_dir)
        out = tmp_path / "consumer"
        out.mkdir()

        _run_main(data_dir, out)
        manifest = json.loads((out / "provenance.json").read_text())

        assert "first_valid_month_ids" not in manifest
        assert "last_valid_month_ids" not in manifest
