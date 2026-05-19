"""GHS-POP viewpoint v1 — spatial aggregation + temporal interpolation.

Reads GHS-POP R2023A GeoTIFF files from the harvest output directory,
aggregates 30-arcsecond pixels to 0.5-degree PRIO-GRID cells (sum),
and interpolates 12 five-year epochs to monthly via step function.

No consolidation layer (ADR-029: single release, nothing to merge).
Viewpoint reads directly from data/raw/ghspop/.

Implements ADR-014 (viewpoints as derived views), ADR-029 (GHS-POP),
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
    compute_content_digest,
)
from datafactory_viewpoint.builders import register_builder
from datafactory_viewpoint.viewpoint_result import ViewpointResult

logger = logging.getLogger(__name__)

DATASET_ID = "ghspop_viewpoint"

KNOWN_EPOCHS = (
    1975, 1980, 1985, 1990, 1995,
    2000, 2005, 2010, 2015, 2020, 2025, 2030,
)

PIXELS_PER_CELL = 60

DEFAULT_NODATA = -200.0

_VIEWS_EPOCH_YEAR = 1980


# ---- Config ----


@dataclass(frozen=True)
class GhsPopViewpointConfig:
    """Configuration for building a GHS-POP viewpoint.

    Reads GeoTIFF files from source_dir (harvest output), aggregates
    to PRIO-GRID resolution, interpolates to monthly, writes Parquet.
    """

    source_dir: Path

    output_path: Path = Path("data/viewpoint/ghspop_v1.parquet")
    ledger_path: Path = Path(
        "provenance/viewpoint/ghspop_v1_ledger.jsonl"
    )

    epochs: tuple[int, ...] = KNOWN_EPOCHS
    release: str = "R2023A"
    resolution: str = "30ss"
    crs: str = "4326"

    aggregation: str = "sum"
    temporal_interpolation: str = "step"

    start_year: int = 1975
    start_month: int = 1
    end_year: int = 2030
    end_month: int = 12

    nodata: float = DEFAULT_NODATA

    version: str = "ghspop_v1"

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

    def tif_filename(self, epoch: int) -> str:
        stem = (
            f"GHS_POP_E{epoch}_GLOBE"
            f"_{self.release}_{self.crs}_{self.resolution}"
        )
        return f"{stem}_V1_0.tif"


# ---- Spatial aggregation ----


def _aggregate_to_prio_grid(
    data: np.ndarray,
    *,
    nodata: float = DEFAULT_NODATA,
) -> np.ndarray:
    """Aggregate 30-arcsecond raster to 0.5-degree PRIO-GRID cells.

    Each PRIO-GRID cell is exactly 60x60 source pixels (WGS84 30ss).
    Aggregation is block-sum via reshape — no reprojection, exact.

    Args:
        data: 2-D float array (nrow, ncol). Dimensions must be
            divisible by 60.
        nodata: Fill value treated as zero.

    Returns:
        2-D array of shape (nrow//60, ncol//60) with population sums.
    """
    nrow, ncol = data.shape
    p = PIXELS_PER_CELL

    if nrow % p != 0 or ncol % p != 0:
        msg = (
            f"Raster dimensions ({nrow}, {ncol}) must be "
            f"divisible by {p}"
        )
        logger.error(msg)
        raise ValueError(msg)

    clean = data.astype(np.float64).copy()
    clean[clean == nodata] = 0.0
    clean[clean < 0.0] = 0.0

    prio_rows = nrow // p
    prio_cols = ncol // p

    blocks = clean.reshape(prio_rows, p, prio_cols, p)
    return blocks.sum(axis=(1, 3))


# ---- Temporal interpolation ----


def _interpolate_temporal(
    epoch_values: dict[int, float],
    *,
    start_year: int,
    start_month: int,
    end_year: int,
    end_month: int,
) -> list[float]:
    """Step-function interpolation from epoch values to monthly.

    For each month, use the value from the most recent epoch that
    is on or before that month. Months before all epochs get 0.

    Args:
        epoch_values: Mapping of epoch year → aggregated value.
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


# ---- Builder ----


def build_ghspop_v1(
    config: GhsPopViewpointConfig | None = None,
    *,
    source_dir: Path | None = None,
) -> ViewpointResult:
    """Build GHS-POP viewpoint v1 from harvested GeoTIFF files.

    For each epoch: read GeoTIFF, aggregate to PRIO-GRID, collect
    per-cell values. Then interpolate all cells temporally and write
    Parquet with (pgid, month_id, pop_count).

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
        config = GhsPopViewpointConfig(source_dir=source_dir)

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
        raw = tifffile.imread(str(tif_path))
        grid = _aggregate_to_prio_grid(raw, nodata=config.nodata)
        epoch_grids[epoch] = grid
        logger.info(
            "Epoch %d: %d×%d → %d×%d cells, total pop %.0f",
            epoch, raw.shape[0], raw.shape[1],
            grid.shape[0], grid.shape[1], grid.sum(),
        )

    prio_rows, prio_cols = next(iter(epoch_grids.values())).shape

    # Build (pgid, month_id, pop_count) rows
    pgid_rows: list[int] = []
    month_id_rows: list[int] = []
    pop_count_rows: list[float] = []

    for row in range(prio_rows):
        for col in range(prio_cols):
            epoch_values = {
                ep: float(grid[row, col])
                for ep, grid in epoch_grids.items()
            }

            monthly = _interpolate_temporal(
                epoch_values,
                start_year=config.start_year,
                start_month=config.start_month,
                end_year=config.end_year,
                end_month=config.end_month,
            )

            # PRIO-GRID ID: row-major from bottom-left
            # Row 0 in raster = north = top of grid = last PRIO row
            prio_row = prio_rows - 1 - row
            pgid = prio_row * prio_cols + col + 1

            for i, pop in enumerate(monthly):
                if pop == 0.0:
                    continue

                year = config.start_year + (
                    config.start_month - 1 + i
                ) // 12
                month = (config.start_month - 1 + i) % 12 + 1
                mid = (year - _VIEWS_EPOCH_YEAR) * 12 + month

                pgid_rows.append(pgid)
                month_id_rows.append(mid)
                pop_count_rows.append(pop)

    # Write Parquet
    table = pa.table({
        "pgid": pa.array(pgid_rows, type=pa.int32()),
        "month_id": pa.array(month_id_rows, type=pa.int32()),
        "pop_count": pa.array(pop_count_rows, type=pa.float64()),
    })

    n_output = table.num_rows

    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, config.output_path)

    output_digest = compute_content_digest(
        config.output_path.read_bytes()
    )

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
        "GHS-POP viewpoint %s built: %d epochs → %d rows "
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


register_builder("ghspop_v1", build_ghspop_v1)
