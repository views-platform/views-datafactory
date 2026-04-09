"""Tests for scripts/generate_consumer_data.py — consumer contract.

Verifies the consumer data generator produces output matching
the views-models training contract: correct columns, index,
renames, row/col derivation, NaN filling, and partition bounds.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

# Load the script as a module (scripts/ is not a package)
_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_consumer_data.py"
_spec = importlib.util.spec_from_file_location("generate_consumer_data", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

generate_partition = _mod.generate_partition
PARTITIONS = _mod.PARTITIONS
FEATURE_RENAME = _mod.FEATURE_RENAME
_forecasting_partition = _mod._forecasting_partition


def _make_consumer_grid(
    data_dir: Path,
    gaul_dir: Path,
    n_t: int = 6,
) -> None:
    """Create a tiny assembled grid with consumer-relevant features."""
    n_h, n_w = 3, 4
    n_cells = n_h * n_w

    # 4 features matching FACTORY_FEATURES
    features = ["ged_sb_best", "ged_ns_best", "ged_os_best", "gaul0_code"]
    grid = np.ones((n_t, n_h, n_w, len(features)), dtype=np.float32)
    # Set ged_sb_best to pgid value for traceability
    pgids = np.arange(1, n_cells + 1).reshape(n_h, n_w)
    for t in range(n_t):
        grid[t, :, :, 0] = pgids  # ged_sb_best = pgid
    grid[:, :, :, 3] = 42  # gaul0_code = 42

    data_dir.mkdir(parents=True, exist_ok=True)
    np.save(data_dir / "grid.npy", grid)
    np.save(data_dir / "pgids.npy", pgids)

    # month_ids 481-486 = 2020-01 to 2020-06
    time_steps = np.array(
        [f"2020-{m:02d}" for m in range(1, n_t + 1)],
        dtype="datetime64[M]",
    )
    np.save(data_dir / "time_steps.npy", time_steps)
    (data_dir / "feature_names.json").write_text(
        json.dumps(features),
    )

    # GAUL parquets
    gaul_dir.mkdir(parents=True, exist_ok=True)
    gids = list(range(1, n_cells + 1))
    name_table = pa.table({
        "gid": gids,
        "value": ["Testland"] * n_cells,
    })
    pq.write_table(name_table, gaul_dir / "gaul0_name.parquet")
    code_table = pa.table({"gid": gids, "value": [42] * n_cells})
    pq.write_table(code_table, gaul_dir / "gaul0_code.parquet")


class TestGeneratePartition:

    def test_correct_columns(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "assembled"
        gaul_dir = tmp_path / "gaul"
        _make_consumer_grid(data_dir, gaul_dir)

        df = generate_partition(
            "test", 481, 486,
            data_dir=data_dir, gaul_dir=gaul_dir,
        )
        assert sorted(df.columns.tolist()) == [
            "c_id", "col", "lr_ns_best", "lr_os_best",
            "lr_sb_best", "row",
        ]

    def test_index_names(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "assembled"
        gaul_dir = tmp_path / "gaul"
        _make_consumer_grid(data_dir, gaul_dir)

        df = generate_partition(
            "test", 481, 486,
            data_dir=data_dir, gaul_dir=gaul_dir,
        )
        assert df.index.names == ["month_id", "priogrid_gid"]

    def test_feature_rename(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "assembled"
        gaul_dir = tmp_path / "gaul"
        _make_consumer_grid(data_dir, gaul_dir)

        df = generate_partition(
            "test", 481, 486,
            data_dir=data_dir, gaul_dir=gaul_dir,
        )
        # ged_sb_best renamed to lr_sb_best
        assert "lr_sb_best" in df.columns
        assert "ged_sb_best" not in df.columns
        # gaul0_code renamed to c_id
        assert "c_id" in df.columns
        assert "gaul0_code" not in df.columns

    def test_row_col_derivation(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "assembled"
        gaul_dir = tmp_path / "gaul"
        _make_consumer_grid(data_dir, gaul_dir)

        df = generate_partition(
            "test", 481, 481,
            data_dir=data_dir, gaul_dir=gaul_dir,
            region="Testland",
        )
        # pgid=1: row=(1-1)//720+1=1, col=(1-1)%720+1=1
        row1 = df.loc[(481, 1), "row"]
        col1 = df.loc[(481, 1), "col"]
        assert row1 == 1.0
        assert col1 == 1.0

    def test_no_nan(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "assembled"
        gaul_dir = tmp_path / "gaul"
        _make_consumer_grid(data_dir, gaul_dir)

        df = generate_partition(
            "test", 481, 486,
            data_dir=data_dir, gaul_dir=gaul_dir,
        )
        assert df.isna().sum().sum() == 0

    def test_sorted_index(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "assembled"
        gaul_dir = tmp_path / "gaul"
        _make_consumer_grid(data_dir, gaul_dir)

        df = generate_partition(
            "test", 481, 486,
            data_dir=data_dir, gaul_dir=gaul_dir,
        )
        assert df.index.is_monotonic_increasing


class TestPartitionBoundaries:

    def test_calibration_matches_models(self) -> None:
        """PARTITIONS must match views-models config_partitions.py."""

        cal = PARTITIONS["calibration"]
        assert cal["train"] == (121, 444)
        assert cal["test"] == (445, 492)

    def test_validation_matches_models(self) -> None:

        val = PARTITIONS["validation"]
        assert val["train"] == (121, 492)
        assert val["test"] == (493, 540)

    def test_forecasting_is_dynamic(self) -> None:

        assert PARTITIONS["forecasting"] is None

    def test_forecasting_partition_computes(self) -> None:
        fp = _forecasting_partition(steps=36)
        assert fp["train"][0] == 121
        assert fp["test"][1] == fp["test"][0] + 36


class TestFeatureRename:

    def test_rename_map_complete(self) -> None:
        assert FEATURE_RENAME == {
            "ged_sb_best": "lr_sb_best",
            "ged_ns_best": "lr_ns_best",
            "ged_os_best": "lr_os_best",
            "gaul0_code": "c_id",
        }
