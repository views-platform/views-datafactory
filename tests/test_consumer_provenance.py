"""Characterization: consumer parquet provenance (C-254, #199).

Pin the provenance manifest behavior of generate_consumer_data.py.
Source script is NOT modified.
"""

from __future__ import annotations

import importlib.util
import json
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
        names=["month_id", "priogrid_gid"],
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
    with (
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
            "feature_mapping",
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
