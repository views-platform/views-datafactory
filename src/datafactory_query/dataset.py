"""Unified dataset loading — the primary consumer entry point.

Loads a subset of the assembled grid by region, time range,
and features, returning the requested output format.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from datafactory_adapters import FeatureFrame, grid_to_dataframe, grid_to_feature_frame
from datafactory_query.regions import load_region_pgids
from datafactory_query.temporal import parse_time_range, time_range_to_slice

__all__ = ["load_dataset"]

logger = logging.getLogger(__name__)

_VALID_FORMATS = ("feature_frame", "dataframe")


def _load_grid(
    data_dir: Path,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """Load assembled grid + sidecars from disk.

    Returns:
        (grid, pgids, time_steps, feature_names)
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
    return grid, pgids, time_steps, feature_names


def _resolve_feature_indices(
    feature_names: list[str],
    features: list[str],
) -> list[int]:
    """Map requested feature names to indices in the grid."""
    name_to_idx = {n: i for i, n in enumerate(feature_names)}
    indices = []
    for f in features:
        if f not in name_to_idx:
            msg = (
                f"Unknown feature {f!r}. "
                f"Available: {feature_names}"
            )
            raise ValueError(msg)
        indices.append(name_to_idx[f])
    return indices


def _build_spatial_mask(
    pgids: np.ndarray,
    region_pgids: set[int],
) -> np.ndarray:
    """Build a boolean [H, W] mask for cells in the region."""
    flat = np.isin(pgids.ravel(), np.array(sorted(region_pgids)))
    return flat.reshape(pgids.shape)


def load_dataset(
    *,
    region: str = "land",
    start: str | int | None = None,
    end: str | int | None = None,
    features: list[str] | None = None,
    output_format: str = "feature_frame",
    data_dir: Path = Path("data/assembled"),
    gaul_dir: Path = Path("data/raw/gaul_admin"),
    month_id_epoch: int = 1980,
) -> FeatureFrame | pd.DataFrame:
    """Load a subset of the assembled grid.

    This is the primary consumer entry point. Handles temporal
    subsetting, geographic filtering, feature selection, and
    format conversion.

    Args:
        region: Geographic filter. Predefined regions ("africa_me",
            "americas", "europe", "asia_oceania"), special values
            ("global", "land"), or a GAUL country name ("Ethiopia").
        start: Start of time range (inclusive). Accepts "2020",
            "2020-01", "2020-01-15", VIEWS month_id (int), or
            None (dataset start).
        end: End of time range (inclusive). Same formats, or None
            (dataset end).
        features: List of feature names to include. None = all.
        output_format: Output format: "feature_frame" or "dataframe".
        data_dir: Path to assembled grid directory.
        gaul_dir: Path to GAUL admin Parquet files.
        month_id_epoch: Epoch for month_id encoding (default 1980
            = VIEWS convention).

    Returns:
        FeatureFrame or DataFrame depending on output_format.

    Raises:
        ValueError: For invalid region, time range, features, or format.
        FileNotFoundError: If data files are not found.
    """
    if output_format not in _VALID_FORMATS:
        msg = (
            f"Unknown format {output_format!r}. "
            f"Valid: {list(_VALID_FORMATS)}"
        )
        raise ValueError(msg)

    # Load grid
    grid, pgids, time_steps, all_features = _load_grid(data_dir)
    n_t, n_h, n_w, n_f = grid.shape

    # Temporal subsetting
    start_dt, end_dt = parse_time_range(
        start, end, time_steps=time_steps,
    )
    t_slice = time_range_to_slice(time_steps, start_dt, end_dt)
    grid = grid[t_slice]
    time_steps = time_steps[t_slice]

    # Feature subsetting
    if features is not None:
        f_indices = _resolve_feature_indices(all_features, features)
        grid = grid[:, :, :, f_indices]
        all_features = [all_features[i] for i in f_indices]

    # Geographic subsetting → land_pgids for adapters
    region_pgids = load_region_pgids(region, gaul_dir=gaul_dir)

    logger.info(
        "Loading: region=%s (%d cells), time=%s..%s (%d months), "
        "features=%d, format=%s",
        region,
        len(region_pgids),
        time_steps[0],
        time_steps[-1],
        len(time_steps),
        len(all_features),
        output_format,
    )

    # Convert to requested format
    if output_format == "feature_frame":
        return grid_to_feature_frame(
            grid,
            pgids,
            time_steps,
            all_features,
            land_pgids=region_pgids,
            month_id_epoch=month_id_epoch,
        )

    # output_format == "dataframe"
    return grid_to_dataframe(
        grid,
        pgids,
        time_steps,
        all_features,
        land_pgids=region_pgids,
        month_id_epoch=month_id_epoch,
    )
