"""GHS-BUILT-S viewpoint v1 — spatial aggregation + temporal interpolation.

Reads GHS-BUILT-S R2023A GeoTIFF files from the harvest output directory,
aggregates 30-arcsecond pixels to 0.5-degree PRIO-GRID cells (sum),
and interpolates 12 five-year epochs to monthly via linear interpolation.

No consolidation layer (ADR-034: single release, nothing to merge).
Viewpoint reads directly from data/raw/ghsbuilts/.

Implements ADR-014 (viewpoints as derived views), ADR-034 (GHS-BUILT-S),
ADR-030 (tifffile for GeoTIFF I/O).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import tifffile

from datafactory_provenance import (
    DIGEST_SCHEME,
    LEDGER_VERSION,
    append_ledger_entry,
    compute_file_digest,
)
from datafactory_viewpoint.builders import register_builder
from datafactory_viewpoint.viewpoint_result import ViewpointResult

logger = logging.getLogger(__name__)

DATASET_ID = "ghsbuilts_viewpoint"

KNOWN_EPOCHS = (
    1975, 1980, 1985, 1990, 1995,
    2000, 2005, 2010, 2015, 2020, 2025, 2030,
)

PIXELS_PER_CELL = 60

VALID_TEMPORAL_INTERPOLATIONS = ("step", "linear")

_VIEWS_EPOCH_YEAR = 1980


# ---- Config ----


@dataclass(frozen=True)
class GhsBuiltSViewpointConfig:
    """Configuration for building a GHS-BUILT-S viewpoint.

    Reads GeoTIFF files from source_dir (harvest output), aggregates
    to PRIO-GRID resolution, interpolates to monthly, writes Parquet.
    """

    source_dir: Path

    output_path: Path = Path("data/viewpoint/ghsbuilts_v1.parquet")
    ledger_path: Path = Path(
        "provenance/viewpoint/ghsbuilts_v1_ledger.jsonl"
    )

    epochs: tuple[int, ...] = KNOWN_EPOCHS
    release: str = "R2023A"
    resolution: str = "30ss"
    crs: str = "4326"

    aggregation: str = "sum"
    temporal_interpolation: str = "linear"

    start_year: int = 1975
    start_month: int = 1
    end_year: int = 2030
    end_month: int = 12

    version: str = "ghsbuilts_v1"

    def __post_init__(self) -> None:
        if not self.version:
            err_msg = "version must be non-empty"
            logger.error(err_msg)
            raise ValueError(err_msg)
        if not self.epochs:
            err_msg = "At least one epoch is required"
            logger.error(err_msg)
            raise ValueError(err_msg)
        for epoch in self.epochs:
            if epoch not in KNOWN_EPOCHS:
                err_msg = (
                    f"Unknown epoch {epoch}. "
                    f"Valid epochs: {KNOWN_EPOCHS}"
                )
                logger.error(err_msg)
                raise ValueError(err_msg)
        if self.temporal_interpolation not in VALID_TEMPORAL_INTERPOLATIONS:
            err_msg = (
                f"Unknown temporal_interpolation "
                f"'{self.temporal_interpolation}'. "
                f"Valid: {VALID_TEMPORAL_INTERPOLATIONS}"
            )
            logger.error(err_msg)
            raise ValueError(err_msg)

    def tif_filename(self, epoch: int) -> str:
        stem = (
            f"GHS_BUILT_S_E{epoch}_GLOBE"
            f"_{self.release}_{self.crs}_{self.resolution}"
        )
        return f"{stem}_V1_0.tif"


# ---- Spatial alignment ----

PRIO_NROW = 360
PRIO_NCOL = 720
GLOBE_PIXEL_ROWS = PRIO_NROW * PIXELS_PER_CELL  # 21600
GLOBE_PIXEL_COLS = PRIO_NCOL * PIXELS_PER_CELL  # 43200


def _read_geotiff(
    path: Path,
) -> tuple[np.ndarray, float, float, float, float]:
    """Read GeoTIFF and extract geotransform from TIFF tags.

    Returns native dtype (uint32 for JRC GHS-BUILT-S). No in-memory
    dtype conversion — strip-based aggregation handles any input dtype.

    Returns:
        (data, tiepoint_x, tiepoint_y, pixel_scale_x, pixel_scale_y)
        where tiepoint is the top-left geographic coordinate.
    """
    with tifffile.TiffFile(str(path)) as tif:
        page = tif.pages.first
        data = page.asarray(maxworkers=1)

        scale_tag = page.tags.get("ModelPixelScaleTag")
        tie_tag = page.tags.get("ModelTiepointTag")

        if scale_tag is None or tie_tag is None:
            msg = (
                f"GeoTIFF {path} missing geotransform tags "
                "(ModelPixelScaleTag, ModelTiepointTag)"
            )
            logger.error(msg)
            raise ValueError(msg)

        scale = scale_tag.value
        tie = tie_tag.value

        pixel_scale_x = float(scale[0])
        pixel_scale_y = float(scale[1])
        tiepoint_x = float(tie[3])
        tiepoint_y = float(tie[4])

    return data, tiepoint_x, tiepoint_y, pixel_scale_x, pixel_scale_y


# ---- Spatial aggregation ----


def _aggregate_with_alignment(
    data: np.ndarray,
    row_offset: int,
    col_offset: int,
) -> np.ndarray:
    """Aggregate raw raster to PRIO-GRID via strip processing.

    Combines alignment and aggregation without allocating a full
    21600x43200 globe array. Processes one PRIO-GRID row (60 pixel
    rows) at a time — peak memory is raw_array + ~20 MB instead of
    raw_array + globe_array.

    GHS-BUILT-S is uint32 with no nodata sentinel — zero means
    no built-up surface, which is a legitimate value that sums
    correctly without masking.

    Args:
        data: Raw 2-D raster (e.g. 21384x43201).
        row_offset: Globe pixel row where the raster's first row lands.
        col_offset: Globe pixel column where the raster's first column
            lands.

    Returns:
        2-D float64 array of shape (360, 720) with built-up area sums.
    """
    p = PIXELS_PER_CELL
    result = np.zeros((PRIO_NROW, PRIO_NCOL), dtype=np.float64)

    for prio_row in range(PRIO_NROW):
        globe_r0 = prio_row * p
        raw_r0 = globe_r0 - row_offset
        raw_r1 = raw_r0 + p

        src_r0 = max(0, raw_r0)
        src_r1 = min(data.shape[0], raw_r1)

        if src_r0 >= src_r1:
            continue

        strip = data[src_r0:src_r1, :].astype(np.float64)

        n_rows = strip.shape[0]
        aligned = np.zeros(
            (n_rows, GLOBE_PIXEL_COLS), dtype=np.float64,
        )

        dst_c0 = max(0, col_offset)
        src_c0 = max(0, -col_offset)
        n_cols = min(
            strip.shape[1] - src_c0,
            GLOBE_PIXEL_COLS - dst_c0,
        )
        if n_cols > 0:
            aligned[:, dst_c0:dst_c0 + n_cols] = (
                strip[:, src_c0:src_c0 + n_cols]
            )
        del strip

        blocks = aligned.reshape(n_rows, PRIO_NCOL, p)
        result[prio_row, :] = blocks.sum(
            axis=(0, 2), dtype=np.float64,
        )
        del aligned

    logger.info(
        "Aggregated %dx%d raster to %dx%d PRIO-GRID "
        "(row_offset=%d, col_offset=%d, strip processing)",
        data.shape[0], data.shape[1],
        PRIO_NROW, PRIO_NCOL,
        row_offset, col_offset,
    )

    return result


# ---- Temporal interpolation ----


def _interpolate_temporal(
    epoch_values: dict[int, float],
    *,
    strategy: str,
    start_year: int,
    start_month: int,
    end_year: int,
    end_month: int,
) -> list[float]:
    """Interpolate epoch values to monthly time steps.

    Strategies:
        step — hold last known epoch value until the next epoch.
        linear — linearly interpolate between adjacent epochs;
                 hold flat before the first and after the last.

    Args:
        epoch_values: Mapping of epoch year -> aggregated value.
        strategy: One of VALID_TEMPORAL_INTERPOLATIONS.
        start_year, start_month: First output month.
        end_year, end_month: Last output month (inclusive).

    Returns:
        List of float values, one per month.
    """
    n_months = (
        (end_year - start_year) * 12
        + (end_month - start_month)
        + 1
    )

    sorted_epochs = sorted(epoch_values.keys())

    if strategy == "step":
        return _interp_step(
            n_months, sorted_epochs, epoch_values,
            start_year, start_month,
        )
    if strategy == "linear":
        return _interp_linear(
            n_months, sorted_epochs, epoch_values,
            start_year, start_month,
        )
    msg = (
        f"Unknown interpolation strategy '{strategy}'. "
        f"Valid: {VALID_TEMPORAL_INTERPOLATIONS}"
    )
    raise ValueError(msg)


def _interp_step(
    n_months: int,
    sorted_epochs: list[int],
    epoch_values: dict[int, float],
    start_year: int,
    start_month: int,
) -> list[float]:
    result: list[float] = []
    for i in range(n_months):
        year = start_year + (start_month - 1 + i) // 12
        value = 0.0
        for ep in sorted_epochs:
            if ep <= year:
                value = epoch_values[ep]
            else:
                break
        result.append(value)
    return result


def _interp_linear(
    n_months: int,
    sorted_epochs: list[int],
    epoch_values: dict[int, float],
    start_year: int,
    start_month: int,
) -> list[float]:
    result: list[float] = []
    for i in range(n_months):
        year = start_year + (start_month - 1 + i) // 12
        month = (start_month - 1 + i) % 12 + 1
        t = year + (month - 1) / 12.0

        if not sorted_epochs or t < sorted_epochs[0]:
            result.append(0.0)
            continue

        if t >= sorted_epochs[-1]:
            result.append(epoch_values[sorted_epochs[-1]])
            continue

        for j in range(len(sorted_epochs) - 1):
            ep_lo = sorted_epochs[j]
            ep_hi = sorted_epochs[j + 1]
            if ep_lo <= t < ep_hi:
                frac = (t - ep_lo) / (ep_hi - ep_lo)
                val = (
                    epoch_values[ep_lo] * (1 - frac)
                    + epoch_values[ep_hi] * frac
                )
                result.append(val)
                break

    return result


# ---- Builder ----


def build_ghsbuilts_v1(
    config: GhsBuiltSViewpointConfig | None = None,
    *,
    source_dir: Path | None = None,
) -> ViewpointResult:
    """Build GHS-BUILT-S viewpoint v1 from harvested GeoTIFF files.

    For each epoch: read GeoTIFF, aggregate to PRIO-GRID, collect
    per-cell values. Then interpolate all cells temporally and write
    Parquet with (pgid, month_id, built_area).

    Args:
        config: Full viewpoint configuration. If None, uses defaults
            with source_dir.
        source_dir: Shortcut — used only if config is None.

    Returns:
        ViewpointResult with cell counts and output digest.
    """
    if config is None:
        if source_dir is None:
            err_msg = (
                "Either config or source_dir must be provided"
            )
            logger.error(err_msg)
            raise ValueError(err_msg)
        config = GhsBuiltSViewpointConfig(source_dir=source_dir)

    if not config.source_dir.exists():
        err_msg = f"Source directory not found: {config.source_dir}"
        logger.error(err_msg)
        raise FileNotFoundError(err_msg)

    # Read and aggregate each epoch
    epoch_grids: dict[int, np.ndarray] = {}
    for epoch in config.epochs:
        tif_path = config.source_dir / config.tif_filename(epoch)
        if not tif_path.exists():
            err_msg = (
                f"GeoTIFF not found for epoch {epoch}: {tif_path}"
            )
            logger.error(err_msg)
            raise FileNotFoundError(err_msg)

        logger.info("Reading epoch %d from %s", epoch, tif_path)
        raw, tie_x, tie_y, sc_x, sc_y = _read_geotiff(tif_path)

        row_off = round((90.0 - tie_y) / sc_y)
        col_off = round((tie_x - (-180.0)) / sc_x)
        grid = _aggregate_with_alignment(raw, row_off, col_off)
        del raw

        epoch_grids[epoch] = grid
        logger.info(
            "Epoch %d: -> %dx%d cells, total built area %.0f m^2",
            epoch,
            grid.shape[0], grid.shape[1], grid.sum(),
        )

    prio_rows, prio_cols = next(iter(epoch_grids.values())).shape

    # Build (pgid, month_id, built_area) rows
    pgid_rows: list[int] = []
    month_id_rows: list[int] = []
    built_area_rows: list[float] = []

    for row in range(prio_rows):
        for col in range(prio_cols):
            epoch_values = {
                ep: float(grid[row, col])
                for ep, grid in epoch_grids.items()
            }

            monthly = _interpolate_temporal(
                epoch_values,
                strategy=config.temporal_interpolation,
                start_year=config.start_year,
                start_month=config.start_month,
                end_year=config.end_year,
                end_month=config.end_month,
            )

            # PRIO-GRID ID: row-major from bottom-left
            # Row 0 in raster = north = top of grid = last PRIO row
            prio_row = prio_rows - 1 - row
            pgid = prio_row * prio_cols + col + 1

            for i, area in enumerate(monthly):
                if area == 0.0:
                    continue

                year = config.start_year + (
                    config.start_month - 1 + i
                ) // 12
                month = (config.start_month - 1 + i) % 12 + 1
                mid = (year - _VIEWS_EPOCH_YEAR) * 12 + month

                pgid_rows.append(pgid)
                month_id_rows.append(mid)
                built_area_rows.append(area)

    # Write Parquet
    table = pa.table({
        "pgid": pa.array(pgid_rows, type=pa.int32()),
        "month_id": pa.array(month_id_rows, type=pa.int32()),
        "built_area": pa.array(built_area_rows, type=pa.float64()),
    })
    del pgid_rows, month_id_rows, built_area_rows

    n_output = table.num_rows

    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, config.output_path)

    output_digest = compute_file_digest(config.output_path)

    append_ledger_entry(config.ledger_path, {
        "dataset": DATASET_ID,
        "version": config.version,
        "epochs": list(config.epochs),
        "aggregation": config.aggregation,
        "temporal_interpolation": config.temporal_interpolation,
        "n_epochs": len(config.epochs),
        "n_cells_output": n_output,
        "output_path": str(config.output_path),
        "output_digest": output_digest,
        "outcome": "success",
        "ledger_version": LEDGER_VERSION,
        "digest_algorithm": DIGEST_SCHEME,
    })

    logger.info(
        "GHS-BUILT-S viewpoint %s built: %d epochs -> %d rows "
        "(digest: %s)",
        config.version,
        len(config.epochs),
        n_output,
        output_digest,
    )

    return ViewpointResult(
        output_path=config.output_path,
        n_events_input=sum(
            int(g.size) for g in epoch_grids.values()
        ),
        n_events_output=n_output,
        n_summary_expanded=0,
        n_filtered=0,
        output_digest=output_digest,
        version=config.version,
    )


register_builder("ghsbuilts_v1", build_ghsbuilts_v1)
