"""Spatial distribution strategy registry for viewpoint building.

Each strategy is a function: (dict, SpatialWeightMap) -> list[dict].
Given a single event and a precomputed weight map, the strategy
returns one or more rows depending on whether the event has low
spatial precision (where_prec >= 4).

Adding a new strategy means adding a function here with the
@_registry.decorator — no changes to the builder (OCP).

Mirrors temporal_distribution.py for the spatial dimension.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable

from datafactory_provenance.registry import Registry
from datafactory_viewpoint.spatial_weights import SpatialWeightMap

logger = logging.getLogger(__name__)

_registry: Registry[
    Callable[[dict, SpatialWeightMap], list[dict]]
] = Registry("spatial distribution strategy")

__all__ = [
    "get_spatial_distribution",
    "proportional",
    "passthrough",
]

_SPATIAL_THRESHOLD: int = 4
_COUNTRY_LEVEL: int = 6


def get_spatial_distribution(
    name: str,
) -> Callable[[dict, SpatialWeightMap], list[dict]]:
    """Look up a spatial distribution strategy by name.

    Raises:
        KeyError: If the strategy name is not registered.
    """
    return _registry.get(name)


def _distribute_value(
    value: int,
    weights: dict[int, float],
) -> dict[int, int]:
    """Distribute an integer value across cells by weight.

    Uses floor for all cells, then adds the integer remainder
    to the cell with the highest weight (tie-break: lowest pgid).
    Guarantees sum(output) == value.
    """
    if not weights:
        return {}

    if value == 0:
        return dict.fromkeys(weights, 0)

    allocated: dict[int, int] = {}
    for pgid, share in weights.items():
        allocated[pgid] = int(math.floor(value * share))

    remainder = value - sum(allocated.values())

    if remainder > 0:
        ranked = sorted(
            weights.items(),
            key=lambda item: (-item[1], item[0]),
        )
        for i in range(remainder):
            pgid = ranked[i % len(ranked)][0]
            allocated[pgid] += 1

    return allocated


def _get_polygon_weights(
    event: dict,
    weight_map: SpatialWeightMap,
) -> tuple[dict[int, float] | None, list[int] | None, int | None]:
    """Determine the target polygon and its weights for an event.

    Returns (weights, all_cells, gaul_code) or (None, None, None)
    if the polygon cannot be determined.
    """
    pgid = event.get("priogrid_gid")
    if pgid is None or pgid == 0:
        logger.warning(
            "Event %s has no priogrid_gid, passing through",
            event.get("id"),
        )
        return None, None, None

    pgid_int = int(pgid)
    where_prec = event.get("where_prec", 1)

    if where_prec >= _COUNTRY_LEVEL:
        gaul_code = weight_map.pgid_to_gaul0.get(pgid_int)
        if gaul_code is None:
            logger.warning(
                "Event %s centroid pgid %d has no gaul0 code "
                "(water/unassigned), passing through",
                event.get("id"),
                pgid_int,
            )
            return None, None, None
        weights = weight_map.country_weights.get(gaul_code)
        all_cells = weight_map.country_all_cells.get(gaul_code)
        return weights, all_cells, gaul_code

    gaul_code = weight_map.pgid_to_gaul1.get(pgid_int)
    if gaul_code is None:
        logger.warning(
            "Event %s centroid pgid %d has no gaul1 code "
            "(water/unassigned), passing through",
            event.get("id"),
            pgid_int,
        )
        return None, None, None
    weights = weight_map.admin1_weights.get(gaul_code)
    all_cells = weight_map.admin1_all_cells.get(gaul_code)
    return weights, all_cells, gaul_code


@_registry.decorator("proportional")
def proportional(
    event: dict,
    weight_map: SpatialWeightMap,
) -> list[dict]:
    """Distribute imprecise events proportionally to well-located fatalities.

    For events with where_prec >= 4: determines the target polygon
    (admin-1 for 4/5, country for 6+), distributes best/low/high
    proportionally across the polygon's cells using the precomputed
    weight map. Conserves totals exactly via floor+remainder.

    For where_prec <= 3 or when the polygon cannot be determined:
    returns the event unchanged.
    """
    where_prec = event.get("where_prec", 1)
    if where_prec < _SPATIAL_THRESHOLD:
        return [event]

    weights, all_cells, gaul_code = _get_polygon_weights(
        event, weight_map,
    )
    if weights is None and all_cells is None:
        return [event]

    if weights is None or len(weights) == 0:
        if all_cells and len(all_cells) > 0:
            weights = {
                pgid: 1.0 / len(all_cells) for pgid in all_cells
            }
        else:
            return [event]

    best = int(event.get("best") or 0)
    low = int(event.get("low") or 0)
    high = int(event.get("high") or 0)

    best_alloc = _distribute_value(best, weights)
    low_alloc = _distribute_value(low, weights)
    high_alloc = _distribute_value(high, weights)

    original_pgid = event.get("priogrid_gid")
    n_cells = len(weights)

    rows: list[dict] = []
    for pgid in sorted(weights.keys()):
        row = {
            **event,
            "priogrid_gid": pgid,
            "best": best_alloc[pgid],
            "low": low_alloc[pgid],
            "high": high_alloc[pgid],
            "_spatial_distributed": True,
            "_spatial_source_pgid": original_pgid,
            "_spatial_polygon_code": gaul_code,
            "_spatial_n_cells": n_cells,
        }
        rows.append(row)

    return rows


@_registry.decorator("passthrough")
def passthrough(
    event: dict,
    weight_map: SpatialWeightMap,  # noqa: ARG001
) -> list[dict]:
    """Return event unchanged regardless of where_prec.

    Legacy / production-parity behavior: no spatial distribution.
    """
    return [event]
