"""V-Dem viewpoint v1 — country-year to grid-monthly broadcast.

Reads V-Dem harvest output (country-year Parquet), applies ISO3→pgid
crosswalk via GAUL admin boundaries, and expands annual values to
monthly (step function: constant within each year).

No consolidation layer (ADR-035: single annual release).
Viewpoint reads directly from data/raw/vdem/.

Implements ADR-014 (viewpoints as derived views), ADR-035 (V-Dem).
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
from datafactory_viewpoint.viewpoint_result import ViewpointResult

logger = logging.getLogger(__name__)

DATASET_ID = "vdem_viewpoint"

VDEM_VARIABLES: tuple[str, ...] = (
    "v2xcl_dmove",
    "v2xeg_eqdr",
    "v2xpe_exlsocgr",
    "v2x_clphy",
    "v2xcl_prpty",
    "v2x_ex_military",
    "v2x_ex_party",
    "v2x_horacc",
    "v2xnp_client",
    "v2xnp_regcorr",
    "v2xpe_exlgeo",
    "v2x_veracc",
    "v2xpe_exlpol",
    "v2x_diagacc",
    "v2x_divparctrl",
    "v2xeg_eqprotec",
    "v2x_genpp",
    "v2xpe_exlgender",
    "v2x_hosabort",
    "v2x_libdem",
    "v2xcl_rol",
    "v2x_accountability",
)


# ---- Config ----


@dataclass(frozen=True)
class VdemViewpointConfig:
    """Configuration for building a V-Dem viewpoint.

    Reads harvest Parquet (country-year), applies ISO3→pgid
    crosswalk from GAUL, expands annual to monthly, writes
    Parquet with (pgid, month_id, variable_columns).
    """

    source_path: Path = field(
        default_factory=lambda: Path(
            "data/raw/vdem/vdem_v16.parquet"
        )
    )
    crosswalk_path: Path = field(
        default_factory=lambda: Path(
            "data/raw/gaul_admin/iso3_code.parquet"
        )
    )

    output_path: Path = Path("data/viewpoint/vdem_v1.parquet")
    ledger_path: Path = Path(
        "provenance/viewpoint/vdem_v1_ledger.jsonl"
    )

    variables: tuple[str, ...] = VDEM_VARIABLES

    start_year: int = 1980
    end_year: int = 2025

    version: str = "vdem_v1"

    def __post_init__(self) -> None:
        if not self.version:
            msg = "version must be non-empty"
            logger.error(msg)
            raise ValueError(msg)
        if not self.variables:
            msg = "variables must be non-empty"
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

    @classmethod
    def from_shortcuts(
        cls,
        *,
        source_path: Path | None = None,
        crosswalk_path: Path | None = None,
    ) -> VdemViewpointConfig:
        """Construct config from shortcut arguments."""
        kwargs: dict = {}
        if source_path is not None:
            kwargs["source_path"] = source_path
        if crosswalk_path is not None:
            kwargs["crosswalk_path"] = crosswalk_path
        return cls(**kwargs)


# ---- Crosswalk ----


def _build_iso3_to_pgids(
    crosswalk_path: Path,
) -> dict[str, list[int]]:
    """Build ISO3 → list[pgid] mapping from GAUL iso3_code.parquet.

    The GAUL harvester writes iso3_code.parquet with columns
    (gid, value) where gid is pgid and value is ISO3 alpha-3.
    """
    table = pq.read_table(crosswalk_path)
    gids = table.column("gid").to_pylist()
    iso3s = table.column("value").to_pylist()

    mapping: dict[str, list[int]] = {}
    for gid, iso3 in zip(gids, iso3s, strict=True):
        if iso3 is None or iso3 == "":
            continue
        iso3_str = str(iso3)
        if iso3_str not in mapping:
            mapping[iso3_str] = []
        mapping[iso3_str].append(int(gid))

    logger.info(
        "Crosswalk: %d ISO3 codes → %d pgids",
        len(mapping),
        sum(len(v) for v in mapping.values()),
    )
    return mapping


# ---- Builder ----


def build_vdem_v1(
    config: VdemViewpointConfig,
) -> ViewpointResult:
    """Build V-Dem viewpoint v1 from harvested country-year data.

    For each (country, year): look up pgids via GAUL crosswalk,
    create 12 monthly rows (step function), write Parquet with
    (pgid, month_id, variable_columns).

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

    # Build ISO3 → pgids mapping
    iso3_to_pgids = _build_iso3_to_pgids(config.crosswalk_path)

    # Read harvest output
    source_table = pq.read_table(config.source_path)
    n_input = source_table.num_rows

    iso3_col = source_table.column(
        "country_text_id"
    ).to_pylist()
    year_col = source_table.column("year").to_pylist()
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

    # Expand country-year → (pgid, month_id, variables)
    unmapped_countries: set[str] = set()
    n_filtered = 0

    pgid_chunks: list[np.ndarray] = []
    month_chunks: list[np.ndarray] = []
    var_chunks: dict[str, list[np.ndarray]] = {
        var: [] for var in config.variables
    }

    months_12 = np.arange(1, 13, dtype=np.int32)

    for i in range(n_input):
        iso3 = str(iso3_col[i])
        year = int(year_col[i])

        if year < config.start_year or year > config.end_year:
            n_filtered += 1
            continue

        pgids = iso3_to_pgids.get(iso3)
        if pgids is None:
            unmapped_countries.add(iso3)
            continue

        pgid_arr = np.array(pgids, dtype=np.int32)
        n_pgids = len(pgid_arr)
        base_mid = (year - VIEWS_EPOCH_YEAR) * 12

        month_ids = np.repeat(months_12 + base_mid, n_pgids)
        pgid_tiled = np.tile(pgid_arr, 12)

        pgid_chunks.append(pgid_tiled)
        month_chunks.append(month_ids)
        for var in config.variables:
            val = float(var_arrays[var][i])
            var_chunks[var].append(
                np.full(12 * n_pgids, val, dtype=np.float64),
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

    if unmapped_countries:
        logger.warning(
            "%d V-Dem countries not in GAUL crosswalk: %s",
            len(unmapped_countries),
            sorted(unmapped_countries)[:10],
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
        "unmapped_countries": len(unmapped_countries),
        "n_filtered_years": n_filtered,
        "year_range": [config.start_year, config.end_year],
        "output_path": str(config.output_path),
        "output_digest": output_digest,
        "outcome": "success",
        "ledger_version": LEDGER_VERSION,
        "digest_algorithm": DIGEST_SCHEME,
    })

    logger.info(
        "V-Dem viewpoint %s built: %d input → %d output rows "
        "(%d variables, %d unmapped countries, digest: %s)",
        config.version,
        n_input,
        n_output,
        len(config.variables),
        len(unmapped_countries),
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


register_builder("vdem_v1", build_vdem_v1)
