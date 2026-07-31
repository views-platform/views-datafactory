"""Unified dataset loading — the primary consumer entry point.

Loads a subset of the assembled grid by region, time range,
and features, returning the requested output format.

Supports both local npy directories and zarr stores (local or
remote via HTTP). Pass a Path for npy, or a string ending in
.zarr (local path or URL) for zarr access.
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:  # annotations only — pandas is an optional extra
    import pandas as pd

from datafactory_adapters import (
    FeatureFrame,
    grid_to_country_month,
    grid_to_dataframe,
    grid_to_feature_frame,
)
from datafactory_query.backends_npy import _load_grid_from_npy
from datafactory_query.backends_zarr import (
    _is_remote,
    _load_grid_from_zarr,
    _resolve_storage_options,
    _use_zarr_loader,
)
from datafactory_query.coverage import _warn_pre_coverage
from datafactory_query.output_format import OutputFormat
from datafactory_query.regions import load_region_pgids
from datafactory_query.temporal import parse_time_range, time_range_to_slice

__all__ = ["load_dataset"]

logger = logging.getLogger(__name__)

# Internal alias — the public contract is OutputFormat (ADR-050).
_VALID_FORMATS = tuple(f.value for f in OutputFormat)


def _load_grid(
    data_dir: Path | str,
    *,
    start: str | int | None = None,
    end: str | int | None = None,
    feature_sel: list[str] | None = None,
    storage_options: dict | None = None,
) -> tuple[
    np.ndarray, np.ndarray, np.ndarray, list[str],
    int | None, dict[str, int],
    dict[str, str] | None, dict[str, list[str]],
]:
    """Load assembled grid from npy directory or zarr store.

    For zarr stores, start/end and feature_sel are applied lazily
    before materializing — avoiding full-grid downloads for remote
    stores when only a subset is needed.

    Returns:
        (grid, pgids, time_steps, feature_names,
         last_valid_month_id, first_valid_month_ids,
         feature_agg_types, source_features)
    """
    if _use_zarr_loader(data_dir):
        # Caller-supplied credentials win; netrc is the fallback, not
        # the only option. A consumer authenticating with a bearer
        # token, an API key or a service account has no netrc entry to
        # write, and before this seam existed its only routes were to
        # synthesise a netrc file or fork the package.
        #
        # Remote-only, mirroring _resolve_storage_options, which
        # returns None for local paths: fsspec options are meaningless
        # for a directory on disk and xarray rejects them outright, so
        # honouring them there would turn a harmless argument into a
        # FileNotFoundError. Caught by the local-store test below.
        if not _is_remote(str(data_dir)):
            resolved = None
        elif storage_options is not None:
            resolved = storage_options
        else:
            resolved = _resolve_storage_options(str(data_dir))
        return _load_grid_from_zarr(
            str(data_dir),
            resolved,
            start=start,
            end=end,
            feature_sel=feature_sel,
        )
    return _load_grid_from_npy(Path(data_dir))


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


def load_dataset(
    *,
    region: str = "land",
    start: str | int | None = None,
    end: str | int | None = None,
    features: list[str] | None = None,
    output_format: str = "feature_frame",
    data_dir: Path | str = Path("data/assembled"),
    gaul_dir: Path = Path("data/raw/gaul_admin"),
    month_id_epoch: int = 1980,
    storage_options: dict | None = None,
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
        output_format: Output format: "feature_frame", "dataframe",
            or "country_month" (sums grid cells per country).
        data_dir: Path to assembled grid directory (npy), or string
            path/URL to a zarr store.
        gaul_dir: Path to GAUL admin Parquet files.
        month_id_epoch: Epoch for month_id encoding (default 1980
            = VIEWS convention).
        storage_options: fsspec storage options for a remote zarr
            store — the escape hatch for callers whose credentials
            do not live in `~/.netrc`. Passed through untouched to
            the zarr backend. When None (the default), credentials
            are resolved from `~/.netrc` exactly as before, so
            existing callers are unaffected. Ignored for local npy
            directories, which need no credentials.

            A service authenticating with a bearer token rather
            than HTTP basic auth::

                load_dataset(
                    data_dir="https://store.example/grid.zarr",
                    storage_options={"client_kwargs": {
                        "headers": {"Authorization": f"Bearer {tok}"},
                    }},
                )

            Note this is an fsspec/aiohttp dict, not a datafactory
            type — deliberately, so a new auth mechanism needs no
            change here (ADR-026 governs how credentials are
            *resolved*, not how they are *transported*).

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

    # Auto-include gaul0_code for country_month aggregation
    _country_feature = "gaul0_code"
    feature_sel = features
    if (
        output_format == "country_month"
        and features is not None
        and _country_feature not in features
    ):
        feature_sel = [*features, _country_feature]

    # Load grid. For zarr: time/feature subsetting applied lazily
    # inside _load_grid_from_zarr (single open, no probe).
    # For npy: full grid loaded via mmap, subsetted after.
    is_zarr = _use_zarr_loader(data_dir)
    (
        grid, pgids, time_steps, all_features,
        last_valid_month_id, first_valid_month_ids,
        feature_agg_types, source_features,
    ) = _load_grid(
        data_dir,
        start=start if is_zarr else None,
        end=end if is_zarr else None,
        feature_sel=feature_sel if is_zarr else None,
        storage_options=storage_options,
    )

    # For npy (or zarr with no time args): post-slice
    if not is_zarr:
        start_dt, end_dt = parse_time_range(
            start, end, time_steps=time_steps,
        )
        t_slice = time_range_to_slice(
            time_steps, start_dt, end_dt,
        )
        grid = grid[t_slice]
        time_steps = time_steps[t_slice]

    # Warn if loaded data extends beyond observed UCDP data
    if last_valid_month_id is not None and len(time_steps) > 0:
        from datafactory_priogrid import to_views_month_id

        effective_end_mid = int(to_views_month_id(time_steps[-1]))
        if effective_end_mid > last_valid_month_id:
            warnings.warn(
                f"Loaded data through month {effective_end_mid} "
                f"exceeds last observed data month "
                f"({last_valid_month_id}). Months "
                f"{last_valid_month_id + 1}–{effective_end_mid} "
                f"contain zeros, not observed data.",
                stacklevel=2,
            )

    # Warn if loaded data starts before a source's coverage
    if first_valid_month_ids and len(time_steps) > 0:
        from datafactory_priogrid import to_views_month_id

        effective_start_mid = int(
            to_views_month_id(time_steps[0])
        )
        requested = set(feature_sel or all_features)
        _warn_pre_coverage(
            effective_start_mid,
            first_valid_month_ids,
            requested,
            source_features,
        )

    # Feature subsetting (npy path — zarr already subsetted)
    if feature_sel is not None and not is_zarr:
        f_indices = _resolve_feature_indices(all_features, feature_sel)
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

    if output_format == "country_month":
        return grid_to_country_month(
            grid,
            pgids,
            time_steps,
            all_features,
            land_pgids=region_pgids,
            month_id_epoch=month_id_epoch,
            feature_agg_types=feature_agg_types,
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
