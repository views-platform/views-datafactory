"""SHDI viewpoint v1 — GDL region-year to grid-monthly broadcast.

Reads SHDI harvest output (GDL region-year Parquet), applies GDL→pgid
crosswalk from the SHDI harvester's spatial join, and expands annual
values to monthly (step function: constant within each year).

No consolidation layer (ADR-036: single periodic release).
Viewpoint reads directly from data/raw/shdi/.

SHDI is an intensive quantity (ADR-040): sums are meaningless.
Invariants are value range [0, 1] and completeness.

Implements ADR-014 (viewpoints as derived views), ADR-036 (SHDI).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from datafactory_provenance import (
    DIGEST_SCHEME,
    LEDGER_VERSION,
    VIEWS_EPOCH_YEAR,
    append_ledger_entry,
    compute_file_digest,
)
from datafactory_viewpoint.builders import register_builder
from datafactory_viewpoint.temporal import (
    VALID_TEMPORAL_INTERPOLATIONS,
    interpolate_temporal,
)
from datafactory_viewpoint.viewpoint_result import ViewpointResult

logger = logging.getLogger(__name__)

DATASET_ID = "shdi_viewpoint"

SHDI_VARIABLES: tuple[str, ...] = (
    "shdi",
    "healthindex",
    "edindex",
    "incindex",
)


# ---- Config ----


@dataclass(frozen=True)
class ShdiViewpointConfig:
    """Configuration for building an SHDI viewpoint.

    Reads harvest Parquet (GDL region-year), applies GDL→pgid
    crosswalk, expands annual to monthly, writes Parquet with
    (pgid, month_id, shdi, healthindex, edindex, incindex).
    """

    source_path: Path = field(
        default_factory=lambda: Path(
            "data/raw/shdi/shdi_v10.2.parquet"
        )
    )
    crosswalk_path: Path = field(
        default_factory=lambda: Path(
            "data/raw/shdi/gdl_to_pgid.parquet"
        )
    )

    output_path: Path = Path("data/viewpoint/shdi_v1.parquet")
    ledger_path: Path = Path(
        "provenance/viewpoint/shdi_v1_ledger.jsonl"
    )

    variables: tuple[str, ...] = SHDI_VARIABLES

    start_year: int = 1990
    end_year: int = 2023

    temporal_interpolation: str = "step"

    version: str = "shdi_v1"

    def __post_init__(self) -> None:
        if not self.version:
            msg = "version must be non-empty"
            logger.error(msg)
            raise ValueError(msg)
        if not self.variables:
            msg = "variables must be non-empty"
            logger.error(msg)
            raise ValueError(msg)
        if (
            self.temporal_interpolation
            not in VALID_TEMPORAL_INTERPOLATIONS
        ):
            msg = (
                f"temporal_interpolation "
                f"'{self.temporal_interpolation}' not in "
                f"{VALID_TEMPORAL_INTERPOLATIONS}"
            )
            logger.error(msg)
            raise ValueError(msg)
        if self.start_year < VIEWS_EPOCH_YEAR:
            msg = (
                f"start_year {self.start_year} is before "
                f"VIEWS epoch {VIEWS_EPOCH_YEAR}"
            )
            logger.error(msg)
            raise ValueError(msg)
        if self.end_year < self.start_year:
            msg = (
                f"end_year {self.end_year} < "
                f"start_year {self.start_year}"
            )
            logger.error(msg)
            raise ValueError(msg)


# ---- Crosswalk ----


def _build_gdl_to_pgids(
    crosswalk_path: Path,
) -> dict[str, list[int]]:
    """Build GDL code → list[pgid] mapping from gdl_to_pgid.parquet.

    The SHDI harvester writes gdl_to_pgid.parquet with columns
    (gid, gdl_code) where gid is pgid and gdl_code is GDL region.
    """
    table = pq.read_table(crosswalk_path)
    gids = table.column("gid").to_pylist()
    gdl_codes = table.column("gdl_code").to_pylist()

    mapping: dict[str, list[int]] = {}
    for gid, gdl_code in zip(gids, gdl_codes, strict=True):
        if gdl_code is None or gdl_code == "":
            continue
        code_str = str(gdl_code)
        if code_str not in mapping:
            mapping[code_str] = []
        mapping[code_str].append(int(gid))

    logger.info(
        "Crosswalk: %d GDL codes → %d pgids",
        len(mapping),
        sum(len(v) for v in mapping.values()),
    )
    return mapping


# ---- Builder ----


def build_shdi_v1(
    config: ShdiViewpointConfig,
) -> ViewpointResult:
    """Build SHDI viewpoint v1 from harvested GDL region-year data.

    For each (GDLCODE, Year): look up pgids via GDL crosswalk,
    create 12 monthly rows (step function), write Parquet with
    (pgid, month_id, shdi, healthindex, edindex, incindex).

    Returns:
        ViewpointResult with row counts and output digest.
    """
    if not config.source_path.exists():
        msg = f"Source file not found: {config.source_path}"
        logger.error(msg)
        raise FileNotFoundError(msg)

    if not config.crosswalk_path.exists():
        msg = (
            f"Crosswalk file not found: {config.crosswalk_path}"
        )
        logger.error(msg)
        raise FileNotFoundError(msg)

    # Build GDL → pgids mapping
    gdl_to_pgids = _build_gdl_to_pgids(config.crosswalk_path)

    # Read harvest output
    source_table = pq.read_table(config.source_path)
    n_input = source_table.num_rows

    gdl_col = source_table.column("GDLCODE").to_pylist()
    year_col = source_table.column("Year").to_pylist()
    var_arrays = {
        var: source_table.column(var).to_numpy(
            zero_copy_only=False
        )
        for var in config.variables
        if var in source_table.column_names
    }
    del source_table

    missing_vars = (
        set(config.variables) - set(var_arrays.keys())
    )
    if missing_vars:
        msg = (
            f"Source Parquet missing variables: "
            f"{sorted(missing_vars)}"
        )
        logger.error(msg)
        raise ValueError(msg)

    # Phase 1: group source rows by region, building epoch dicts
    unmapped_regions: set[str] = set()
    n_filtered = 0

    region_epochs: dict[
        str, dict[str, dict[int, float]]
    ] = {}

    for i in range(n_input):
        gdl_code = str(gdl_col[i])
        year = int(year_col[i])

        if year < config.start_year or year > config.end_year:
            n_filtered += 1
            continue

        if gdl_to_pgids.get(gdl_code) is None:
            unmapped_regions.add(gdl_code)
            continue

        if gdl_code not in region_epochs:
            region_epochs[gdl_code] = {
                var: {} for var in config.variables
            }
        for var in config.variables:
            region_epochs[gdl_code][var][year] = float(
                var_arrays[var][i]
            )

    # Phase 2: interpolate via shared temporal module, expand
    pgid_chunks: list[np.ndarray] = []
    month_chunks: list[np.ndarray] = []
    var_chunks: dict[str, list[np.ndarray]] = {
        var: [] for var in config.variables
    }

    for gdl_code, var_epoch_map in region_epochs.items():
        pgid_arr = np.array(
            gdl_to_pgids[gdl_code], dtype=np.int32
        )
        n_pgids = len(pgid_arr)

        first_var = next(iter(var_epoch_map))
        years_present = sorted(
            var_epoch_map[first_var].keys()
        )
        min_year = years_present[0]
        max_year = years_present[-1]

        monthly_vals: dict[str, list[float]] = {}
        for var, epochs in var_epoch_map.items():
            monthly_vals[var] = interpolate_temporal(
                epochs,
                strategy=config.temporal_interpolation,
                start_year=min_year,
                start_month=1,
                end_year=max_year,
                end_month=12,
            )

        n_months = len(monthly_vals[first_var])
        month_id_arr = np.array(
            [
                (min_year - VIEWS_EPOCH_YEAR) * 12 + m + 1
                for m in range(n_months)
            ],
            dtype=np.int32,
        )

        pgid_chunks.append(np.tile(pgid_arr, n_months))
        month_chunks.append(
            np.repeat(month_id_arr, n_pgids)
        )
        for var in config.variables:
            vals = np.array(
                monthly_vals[var], dtype=np.float64
            )
            var_chunks[var].append(
                np.repeat(vals, n_pgids)
            )

    empty_i32 = np.array([], dtype=np.int32)
    empty_f64 = np.array([], dtype=np.float64)
    pgid_rows = (
        np.concatenate(pgid_chunks) if pgid_chunks
        else empty_i32
    )
    month_id_rows = (
        np.concatenate(month_chunks) if month_chunks
        else empty_i32
    )
    var_rows: dict[str, np.ndarray] = {}
    for var in config.variables:
        chunks = var_chunks[var]
        var_rows[var] = (
            np.concatenate(chunks) if chunks else empty_f64
        )

    if unmapped_regions:
        logger.warning(
            "%d SHDI regions not in GDL crosswalk: %s",
            len(unmapped_regions),
            sorted(unmapped_regions)[:10],
        )

    if n_filtered > 0:
        logger.info(
            "Filtered %d rows outside year range %d–%d",
            n_filtered, config.start_year, config.end_year,
        )

    n_output = len(pgid_rows)
    if n_output == 0:
        msg = "Viewpoint produced zero output rows"
        logger.error(msg)
        raise ValueError(msg)

    # Build Arrow table
    columns: dict[str, pa.Array] = {
        "pgid": pa.array(pgid_rows, type=pa.int32()),
        "month_id": pa.array(month_id_rows, type=pa.int32()),
    }
    for var in config.variables:
        columns[var] = pa.array(
            var_rows[var], type=pa.float64()
        )
    del pgid_rows, month_id_rows, var_rows

    table = pa.table(columns)

    # Write Parquet
    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, config.output_path, compression="snappy")

    output_digest = compute_file_digest(config.output_path)

    # Provenance
    append_ledger_entry(config.ledger_path, {
        "dataset": DATASET_ID,
        "version": config.version,
        "n_input_rows": n_input,
        "n_output_rows": n_output,
        "n_variables": len(config.variables),
        "unmapped_regions": len(unmapped_regions),
        "n_filtered_years": n_filtered,
        "year_range": [config.start_year, config.end_year],
        "output_path": str(config.output_path),
        "output_digest": output_digest,
        "outcome": "success",
        "ledger_version": LEDGER_VERSION,
        "digest_algorithm": DIGEST_SCHEME,
    })

    logger.info(
        "SHDI viewpoint %s built: %d input → %d output rows "
        "(%d variables, %d unmapped regions, digest: %s)",
        config.version,
        n_input,
        n_output,
        len(config.variables),
        len(unmapped_regions),
        output_digest,
    )

    return ViewpointResult(
        output_path=config.output_path,
        n_events_input=n_input,
        n_events_output=n_output,
        n_summary_expanded=0,
        n_filtered=n_filtered,
        output_digest=output_digest,
        version=config.version,
    )


register_builder("shdi_v1", build_shdi_v1)
