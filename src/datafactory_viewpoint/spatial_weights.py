"""Spatial weight map for proportional distribution of imprecise events.

Computes per-cell fatality weights within admin-1 and country polygons
using GAUL crosswalk parquets and well-located events from the
consolidated UCDP store. Used by spatial_distribution.py strategies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)

__all__ = ["SpatialWeightMap", "build_spatial_weight_map"]

_WELL_LOCATED_MAX: int = 3


@dataclass(frozen=True)
class SpatialWeightMap:
    """Precomputed cell-level fatality weights within GAUL polygons.

    For each admin-1 and country polygon, stores the proportional
    share of well-located fatalities in each cell. Shares sum to
    1.0 per polygon. Used by spatial distribution strategies to
    allocate imprecise-event deaths.

    Attributes:
        admin1_weights: gaul1_code -> {pgid: share}. Only polygons
            with nonzero well-located fatalities.
        country_weights: gaul0_code -> {pgid: share}. Same rule.
        pgid_to_gaul1: pgid -> gaul1_code for all valid cells.
        pgid_to_gaul0: pgid -> gaul0_code for all valid cells.
        admin1_all_cells: gaul1_code -> [pgids] for uniform fallback.
        country_all_cells: gaul0_code -> [pgids] for uniform fallback.
    """

    admin1_weights: dict[int, dict[int, float]] = field(
        default_factory=dict,
    )
    country_weights: dict[int, dict[int, float]] = field(
        default_factory=dict,
    )
    pgid_to_gaul1: dict[int, int] = field(default_factory=dict)
    pgid_to_gaul0: dict[int, int] = field(default_factory=dict)
    admin1_all_cells: dict[int, list[int]] = field(
        default_factory=dict,
    )
    country_all_cells: dict[int, list[int]] = field(
        default_factory=dict,
    )


def _load_gaul_crosswalk(path: Path) -> dict[int, int]:
    """Load a GAUL crosswalk parquet (gid, value) -> {pgid: gaul_code}.

    Filters out cells with value == -1 (unassigned / water).
    """
    if not path.exists():
        err_msg = f"GAUL crosswalk not found: {path}"
        logger.error(err_msg)
        raise FileNotFoundError(err_msg)

    table = pq.read_table(path)
    gids = table.column("gid").to_pylist()
    values = table.column("value").to_pylist()

    mapping: dict[int, int] = {}
    for gid, val in zip(gids, values, strict=True):
        if val is None or val == -1:
            continue
        mapping[int(gid)] = int(val)

    return mapping


def _build_all_cells(
    pgid_to_gaul: dict[int, int],
) -> dict[int, list[int]]:
    """Invert pgid->gaul_code to gaul_code->[pgids]."""
    result: dict[int, list[int]] = {}
    for pgid, gaul_code in pgid_to_gaul.items():
        if gaul_code not in result:
            result[gaul_code] = []
        result[gaul_code].append(pgid)
    for cells in result.values():
        cells.sort()
    return result


def _compute_weights(
    cell_fatalities: dict[int, float],
    pgid_to_gaul: dict[int, int],
) -> dict[int, dict[int, float]]:
    """Compute proportional weights per polygon from cell fatalities.

    For each polygon, the share of each cell is:
        cell_share = cell_fatalities / polygon_total_fatalities

    Only polygons with nonzero total fatalities are included.
    """
    polygon_totals: dict[int, float] = {}
    polygon_cells: dict[int, dict[int, float]] = {}

    for pgid, deaths in cell_fatalities.items():
        gaul_code = pgid_to_gaul.get(pgid)
        if gaul_code is None:
            continue
        if gaul_code not in polygon_totals:
            polygon_totals[gaul_code] = 0.0
            polygon_cells[gaul_code] = {}
        polygon_totals[gaul_code] += deaths
        polygon_cells[gaul_code][pgid] = (
            polygon_cells[gaul_code].get(pgid, 0.0) + deaths
        )

    weights: dict[int, dict[int, float]] = {}
    for gaul_code, total in polygon_totals.items():
        if total <= 0:
            continue
        weights[gaul_code] = {
            pgid: deaths / total
            for pgid, deaths in polygon_cells[gaul_code].items()
        }

    return weights


def build_spatial_weight_map(
    table: pa.Table,
    gaul1_path: Path,
    gaul0_path: Path,
) -> SpatialWeightMap:
    """Build a spatial weight map from the consolidated event table.

    Scans well-located events (where_prec <= 3), aggregates deaths
    by priogrid_gid, then cross-references with GAUL crosswalks to
    produce per-cell proportional weights within each polygon.

    Args:
        table: Consolidated event table (after stale version filtering).
        gaul1_path: Path to gaul1_code.parquet (pgid -> admin-1 code).
        gaul0_path: Path to gaul0_code.parquet (pgid -> country code).

    Returns:
        SpatialWeightMap with precomputed weights.

    Raises:
        FileNotFoundError: If a GAUL crosswalk parquet is missing.
    """
    pgid_to_gaul1 = _load_gaul_crosswalk(gaul1_path)
    pgid_to_gaul0 = _load_gaul_crosswalk(gaul0_path)

    admin1_all_cells = _build_all_cells(pgid_to_gaul1)
    country_all_cells = _build_all_cells(pgid_to_gaul0)

    logger.info(
        "GAUL crosswalks: %d admin-1 cells, %d country cells",
        len(pgid_to_gaul1),
        len(pgid_to_gaul0),
    )

    well_located_mask = pc.less_equal(
        table.column("where_prec"),
        pa.scalar(_WELL_LOCATED_MAX, type=pa.int64()),
    )
    well_located = table.filter(well_located_mask)

    pgids = well_located.column("priogrid_gid").to_pylist()
    bests = well_located.column("best").to_pylist()

    cell_fatalities: dict[int, float] = {}
    for pgid, best in zip(pgids, bests, strict=True):
        if pgid is None:
            continue
        pgid_int = int(pgid)
        cell_fatalities[pgid_int] = (
            cell_fatalities.get(pgid_int, 0.0) + (best or 0)
        )

    admin1_weights = _compute_weights(cell_fatalities, pgid_to_gaul1)
    country_weights = _compute_weights(cell_fatalities, pgid_to_gaul0)

    logger.info(
        "Spatial weight map: %d admin-1 polygons with weights, "
        "%d country polygons with weights, from %d well-located "
        "events across %d cells",
        len(admin1_weights),
        len(country_weights),
        len(well_located),
        len(cell_fatalities),
    )

    return SpatialWeightMap(
        admin1_weights=admin1_weights,
        country_weights=country_weights,
        pgid_to_gaul1=pgid_to_gaul1,
        pgid_to_gaul0=pgid_to_gaul0,
        admin1_all_cells=admin1_all_cells,
        country_all_cells=country_all_cells,
    )
