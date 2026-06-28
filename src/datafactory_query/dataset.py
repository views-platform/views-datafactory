"""Unified dataset loading — the primary consumer entry point.

Loads a subset of the assembled grid by region, time range,
and features, returning the requested output format.

Supports both local npy directories and zarr stores (local or
remote via HTTP). Pass a Path for npy, or a string ending in
.zarr (local path or URL) for zarr access.
"""

from __future__ import annotations

import json
import logging
import warnings
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import pandas as pd

from datafactory_adapters import (
    FeatureFrame,
    grid_to_country_month,
    grid_to_dataframe,
    grid_to_feature_frame,
)
from datafactory_query.regions import load_region_pgids
from datafactory_query.temporal import parse_time_range, time_range_to_slice

__all__ = ["load_dataset"]

logger = logging.getLogger(__name__)

_VALID_FORMATS = ("feature_frame", "dataframe", "country_month")


def _is_remote(data_dir: Path | str) -> bool:
    """Check if data_dir is a remote URL."""
    if isinstance(data_dir, Path):
        return False
    return "://" in str(data_dir)


def _use_zarr_loader(data_dir: Path | str) -> bool:
    """Check if data_dir should be loaded via the zarr backend.

    True for local paths ending in .zarr or remote URLs with
    .zarr in the path component.
    """
    s = str(data_dir)
    if _is_remote(data_dir):
        return ".zarr" in urlparse(s).path
    return s.endswith(".zarr")


_REMOTE_TIMEOUT_SECONDS = 120


def _resolve_storage_options(
    zarr_path: str,
) -> dict | None:
    """Build fsspec storage options for remote zarr access.

    Reads credentials from ~/.netrc for HTTP URLs.
    Configures aiohttp timeout for network resilience.
    Returns None for local paths.
    """
    if not _is_remote(zarr_path):
        return None

    parsed = urlparse(zarr_path)
    if parsed.scheme not in ("http", "https"):
        return {}

    import aiohttp

    client_kwargs: dict = {
        "timeout": aiohttp.ClientTimeout(
            total=_REMOTE_TIMEOUT_SECONDS,
        ),
    }

    # Try ~/.netrc for credentials
    try:
        from netrc import NetrcParseError, netrc

        nrc = netrc(str(Path.home() / ".netrc"))
        creds = nrc.authenticators(parsed.hostname or "")
        if creds:
            login, _, password = creds
            client_kwargs["auth"] = aiohttp.BasicAuth(
                login, password,
            )
    except (FileNotFoundError, KeyError, NetrcParseError) as exc:
        logger.warning(
            "No credentials for %s: %s. "
            "Remote access may fail with 401.",
            parsed.hostname,
            exc,
        )

    return {"client_kwargs": client_kwargs}


def _load_grid_from_zarr(
    zarr_path: str,
    storage_options: dict | None = None,
    *,
    start: str | int | None = None,
    end: str | int | None = None,
    feature_sel: list[str] | None = None,
) -> tuple[
    np.ndarray, np.ndarray, np.ndarray, list[str],
    int | None, dict[str, int],
    dict[str, str] | None, dict[str, list[str]],
]:
    """Load assembled grid from a zarr store.

    Opens the store once, computes time/feature subsets lazily on
    the xarray Dataset, then materializes only the needed data.
    For remote stores this avoids downloading the full grid.

    Args:
        zarr_path: Local path or URL to zarr store.
        storage_options: fsspec options (auth, timeout, etc.).
        start: Start of time range (passed to parse_time_range).
        end: End of time range (passed to parse_time_range).
        feature_sel: Optional feature names to load (skips others).

    Returns:
        (grid, pgids, time_steps, feature_names,
         last_valid_month_id, first_valid_month_ids,
         feature_agg_types, source_features)
    """
    import xarray as xr

    kwargs: dict = {}
    if storage_options is not None:
        kwargs["storage_options"] = storage_options

    try:
        ds = xr.open_zarr(zarr_path, **kwargs)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        msg = f"Zarr store not found or invalid at {zarr_path}"
        raise FileNotFoundError(msg) from exc
    except OSError as exc:
        exc_msg = str(exc)
        if "401" in exc_msg or "Unauthorized" in exc_msg:
            msg = (
                f"Authentication failed for {zarr_path}. "
                f"Check ~/.netrc credentials."
            )
            raise PermissionError(msg) from exc
        msg = (
            f"Cannot open zarr store at {zarr_path}: "
            f"{type(exc).__name__}: {exc_msg}"
        )
        raise FileNotFoundError(msg) from exc

    pgids = ds["pgid"].values  # [H, W]
    last_valid_month_id: int | None = ds.attrs.get(
        "last_valid_month_id",
    )
    if last_valid_month_id is None:
        warnings.warn(
            f"Zarr store at {zarr_path} lacks 'last_valid_month_id' "
            f"attribute. Zero-padding boundary unknown — consumer "
            f"cannot distinguish observed zeros from padding. "
            f"Re-export with export_zarr.py to fix.",
            UserWarning,
            stacklevel=2,
        )

    # Determine feature order before subsetting
    attrs = ds.attrs
    if "feature_order" in attrs:
        feature_names = list(attrs["feature_order"])
    else:
        warnings.warn(
            f"Zarr store at {zarr_path} lacks 'feature_order' "
            f"attribute. Falling back to sorted(data_vars). "
            f"Feature column order may differ from the npy "
            f"backend. Re-export with export_zarr.py to fix.",
            UserWarning,
            stacklevel=2,
        )
        feature_names = sorted(ds.data_vars)

    # Apply feature subsetting (lazy — no data fetched yet)
    if feature_sel is not None:
        available = set(feature_names)
        missing = [f for f in feature_sel if f not in available]
        if missing:
            msg = (
                f"Unknown feature(s) {missing}. "
                f"Available: {feature_names}"
            )
            raise ValueError(msg)
        feature_names = [
            f for f in feature_names if f in set(feature_sel)
        ]

    # Apply time subsetting (lazy — reduces chunk fetches)
    all_time = ds["time"].values.astype("datetime64[M]")
    if start is not None or end is not None:
        start_dt, end_dt = parse_time_range(
            start, end, time_steps=all_time,
        )
        t_slice = time_range_to_slice(
            all_time, start_dt, end_dt,
        )
        ds = ds.isel(time=t_slice)

    time_steps = ds["time"].values.astype("datetime64[M]")

    # Materialize only the selected features and time range
    grid = np.stack(
        [ds[f].values for f in feature_names], axis=-1,
    ).astype(np.float32)

    ds.close()
    return grid, pgids, time_steps, feature_names, last_valid_month_id, {}, None, {}


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
        for key, val in prov.items():
            if key.startswith("first_valid_") and val is not None:
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


def _load_grid(
    data_dir: Path | str,
    *,
    start: str | int | None = None,
    end: str | int | None = None,
    feature_sel: list[str] | None = None,
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
        storage_options = _resolve_storage_options(str(data_dir))
        return _load_grid_from_zarr(
            str(data_dir),
            storage_options,
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


_SOURCE_DISPLAY_NAMES: dict[str, str] = {
    "acled": "ACLED",
    "ghspop": "GHS-POP",
    "ghsbuilts": "GHS-BUILT-S",
    "vdem": "V-Dem",
    "shdi": "SHDI",
}


def _warn_pre_coverage(
    query_start_mid: int,
    first_valid_month_ids: dict[str, int],
    requested_features: set[str],
    source_features: dict[str, list[str]],
) -> None:
    """Emit UserWarning for each source whose data starts after
    the query's start month, when the query includes features
    from that source (ADR-047, ADR-048, C-156).

    Uses declared source-feature lists from provenance instead
    of prefix inference (ADR-003 compliance).
    """
    for key, first_mid in first_valid_month_ids.items():
        if query_start_mid >= first_mid:
            continue
        source_key = (
            key.removeprefix("first_valid_")
            .removesuffix("_month_id")
        )
        features_key = f"{source_key}_features"
        src_feats = source_features.get(features_key)
        if src_feats is None:
            continue
        src_set = set(src_feats)
        affected = [
            f for f in requested_features if f in src_set
        ]
        if not affected:
            continue
        source_name = _SOURCE_DISPLAY_NAMES.get(
            source_key, source_key,
        )
        warnings.warn(
            f"{source_name} data begins at month_id "
            f"{first_mid}, but query starts at "
            f"{query_start_mid}. Months "
            f"{query_start_mid}–{first_mid - 1} contain "
            f"zero-fill, not observed data. Affected "
            f"features: {affected}",
            UserWarning,
            stacklevel=3,
        )


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
