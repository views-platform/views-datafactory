"""Local npy backend for the assembled grid.

One responsibility: load grid.npy + sidecars (pgids, time_steps,
feature_names, provenance, feature_agg_types) and return the same
tuple shape as the zarr backend. Split from dataset.py per ADR-050
screaming-architecture surgery (#346).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def _load_grid_from_npy(
    data_dir: Path,
) -> tuple[
    np.ndarray, np.ndarray, np.ndarray, list[str],
    int | None, dict[str, int],
    dict[str, str] | None, dict[str, list[str]],
]:
    """Load assembled grid + sidecars from npy files on disk.

    Returns:
        (grid, pgids, time_steps, feature_names,
         last_valid_month_id, first_valid_month_ids,
         feature_agg_types, source_features)
    """
    grid_path = data_dir / "grid.npy"
    if not grid_path.exists():
        msg = (
            f"Assembled grid not found at {grid_path}. "
            f"Run: uv run python scripts/assemble_grid.py"
        )
        raise FileNotFoundError(msg)

    grid = np.load(grid_path, mmap_mode="r")
    pgids = np.load(data_dir / "pgids.npy")
    time_steps = np.load(data_dir / "time_steps.npy")
    feature_names = json.loads(
        (data_dir / "feature_names.json").read_text()
    )

    last_valid_month_id: int | None = None
    first_valid_month_ids: dict[str, int] = {}
    source_features: dict[str, list[str]] = {}
    provenance_path = data_dir / "provenance.json"
    if provenance_path.exists():
        prov = json.loads(provenance_path.read_text())
        last_valid_month_id = prov.get("last_valid_month_id")
        # *_features keys live nested under "sources" in real
        # assembly provenance; synthetic/test provenance may put
        # them top-level. Scan both — reading only the top level
        # silently disabled pre-coverage warnings on real data
        # (found by verify_consumer_contract's first server run,
        # 2026-07-19).
        key_spaces = [prov, prov.get("sources", {})]
        for space in key_spaces:
            for key, val in space.items():
                if (
                    key.startswith("first_valid_")
                    and val is not None
                ):
                    first_valid_month_ids[key] = val
                if key.endswith("_features") and isinstance(val, list):
                    source_features[key] = val

    feature_agg_types: dict[str, str] | None = None
    agg_path = data_dir / "feature_agg_types.json"
    if agg_path.exists():
        agg_list = json.loads(agg_path.read_text())
        if len(agg_list) != len(feature_names):
            msg = (
                f"feature_agg_types.json has {len(agg_list)} "
                f"entries but feature_names has "
                f"{len(feature_names)} — file is corrupt or "
                f"stale (ADR-011)"
            )
            raise RuntimeError(msg)
        feature_agg_types = dict(
            zip(feature_names, agg_list, strict=True),
        )

    return (
        grid, pgids, time_steps, feature_names,
        last_valid_month_id, first_valid_month_ids,
        feature_agg_types, source_features,
    )
