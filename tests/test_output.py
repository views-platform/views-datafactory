"""Direct tests for datafactory_compilation.output."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from datafactory_compilation.output import write_compilation_output


def test_write_compilation_output_creates_files(
    tmp_path: Path,
) -> None:
    """write_compilation_output creates all expected output files."""
    grid = np.zeros((2, 3, 4, 1), dtype=np.float32)
    pgids = np.arange(12, dtype=np.int32).reshape(3, 4)
    time_steps = np.array([1, 2])
    features = ["feat_a"]
    output_dir = tmp_path / "out"
    ledger_path = tmp_path / "ledger.jsonl"
    source_path = tmp_path / "source.parquet"
    source_path.write_bytes(b"fake")

    digest = write_compilation_output(
        grid_array=grid,
        pgids_2d=pgids,
        time_steps=time_steps,
        feature_names=features,
        output_dir=output_dir,
        ledger_path=ledger_path,
        dataset_id="test_dataset",
        source_path=source_path,
        source_digest="sha256:test",
    )

    assert (output_dir / "grid.npy").exists()
    assert (output_dir / "pgids.npy").exists()
    assert (output_dir / "time_steps.npy").exists()
    assert (output_dir / "feature_names.json").exists()
    assert (output_dir / "provenance.json").exists()
    assert ledger_path.exists()
    assert isinstance(digest, str)
    assert len(digest) > 0

    feat = json.loads((output_dir / "feature_names.json").read_text())
    assert feat == ["feat_a"]
