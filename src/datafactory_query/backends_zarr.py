"""Zarr backend for the assembled grid (local or remote).

One responsibility: open a zarr store (with netrc auth for remote
HTTP), read the grid + source metadata attrs, and return the same
tuple shape as the npy backend. Split from dataset.py per ADR-050
screaming-architecture surgery (#346).
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path
from urllib.parse import urlparse

import numpy as np

from datafactory_query.temporal import parse_time_range, time_range_to_slice

logger = logging.getLogger(__name__)

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


def _safe_url(zarr_path: str) -> str:
    """``zarr_path`` with any userinfo masked, for use in messages.

    ``~/.netrc`` is the documented credential path, but nothing stops a
    caller passing ``https://user:pass@host/grid.zarr`` — and this
    module interpolates the store URL into seven error and warning
    messages, any of whose tracebacks land in the caller's log.

    Deliberately local rather than shared with
    ``datafactory_http.retry._redact_url``: ``datafactory_query`` may
    import only ``datafactory_priogrid`` and ``datafactory_adapters``
    (``tests/test_import_enforcement.py``). Second occurrence, not
    third — WET, and widening the allow-list to avoid nine duplicated
    lines would be the more expensive trade.

    Userinfo only. A token in the query string is not a supported way
    to reach this store; netrc is.
    """
    if not _is_remote(zarr_path):
        return zarr_path
    try:
        parsed = urlparse(zarr_path)
    except ValueError:
        # urlparse raises on a malformed authority (unbalanced "[").
        # Return a placeholder rather than the input: a redactor that
        # falls back to its argument emits what it exists to suppress.
        return "<unparseable-url-redacted>"
    if not (parsed.username or parsed.password):
        return zarr_path
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return parsed._replace(netloc=f"***:***@{host}").geturl()


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
        # Type, not instance: CPython's netrc parser embeds the
        # offending token in the message, so an unquoted password
        # containing a space would leak fragments into the log.
        logger.warning(
            "No credentials for %s: %s. "
            "Remote access may fail with 401.",
            parsed.hostname,
            type(exc).__name__,
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
        msg = f"Zarr store not found or invalid at {_safe_url(zarr_path)}"
        raise FileNotFoundError(msg) from exc
    except OSError as exc:
        exc_msg = str(exc)
        if "401" in exc_msg or "Unauthorized" in exc_msg:
            msg = (
                f"Authentication failed for {_safe_url(zarr_path)}. "
                f"Check ~/.netrc credentials."
            )
            raise PermissionError(msg) from exc
        msg = (
            f"Cannot open zarr store at {_safe_url(zarr_path)}: "
            f"{type(exc).__name__}: {exc_msg}"
        )
        raise FileNotFoundError(msg) from exc
    except Exception as exc:
        # aiohttp's ClientResponseError is NOT an OSError, so an HTTP 401
        # from the remote store escaped the mapping above and consumers
        # got a raw client error instead of the documented
        # PermissionError (C-321). Map 401s here; anything else re-raises
        # untouched.
        exc_msg = str(exc)
        if "401" in exc_msg or "Unauthorized" in exc_msg:
            msg = (
                f"Authentication failed for {_safe_url(zarr_path)}. "
                f"Check ~/.netrc credentials."
            )
            raise PermissionError(msg) from exc
        raise

    pgids = ds["pgid"].values  # [H, W]
    last_valid_month_id: int | None = ds.attrs.get(
        "last_valid_month_id",
    )
    if last_valid_month_id is None:
        warnings.warn(
            f"Zarr store at {_safe_url(zarr_path)} lacks 'last_valid_month_id' "
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
            f"Zarr store at {_safe_url(zarr_path)} lacks 'feature_order' "
            f"attribute. Falling back to sorted(data_vars). "
            f"Feature column order may differ from the npy "
            f"backend. Re-export with export_zarr.py to fix.",
            UserWarning,
            stacklevel=2,
        )
        feature_names = sorted(ds.data_vars)

    # Source metadata (C-300): mirrors the npy sidecars so the
    # pre-coverage warning and type-aware aggregation work on the
    # zarr path too. Keyed exactly like provenance.json.
    first_valid_month_ids: dict[str, int] = {}
    source_features: dict[str, list[str]] = {}
    feature_agg_types: dict[str, str] | None = None
    if "source_features" in attrs:
        source_features = {
            k: list(v)
            for k, v in attrs["source_features"].items()
        }
        first_valid_month_ids = {
            k: int(v)
            for k, v in attrs.get(
                "first_valid_month_ids", {},
            ).items()
        }
        agg_list = attrs.get("feature_agg_types")
        if agg_list is not None:
            feature_agg_types = dict(
                zip(feature_names, list(agg_list), strict=True),
            )
    else:
        warnings.warn(
            f"Zarr store at {_safe_url(zarr_path)} lacks source metadata "
            f"attributes (source_features / first_valid_month_ids "
            f"/ feature_agg_types). Pre-coverage warnings and "
            f"type-aware aggregation are unavailable on this "
            f"store. Re-export with export_zarr.py to fix.",
            UserWarning,
            stacklevel=2,
        )

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
    return (
        grid, pgids, time_steps, feature_names,
        last_valid_month_id, first_valid_month_ids,
        feature_agg_types, source_features,
    )
