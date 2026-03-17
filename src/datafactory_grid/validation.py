"""Parity validation: compare our generated grid against a reference source.

Defines a Protocol for reading reference geometry data. The actual
shapefile reader (pyshp, fiona, etc.) is NOT chosen here -- it is
plugged in at call time. This keeps the grid module free of geo
dependencies.

When no reader is available, parity validation simply cannot run.
The grid's self-consistency tests still work.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from datafactory_core import append_ledger_entry
from datafactory_grid.config import GridConfig

logger = logging.getLogger(__name__)


class ReferenceGeometryReader(Protocol):
    """Interface for reading reference grid cell centroids.

    Implementations might use pyshp, fiona, geopandas, or anything
    else that can extract (cell_id, lat, lon) from a shapefile.
    """

    def read(self, path: Path) -> list[tuple[int, float, float]]:
        """Read reference centroids from a file.

        Args:
            path: Path to the shapefile directory or file.

        Returns:
            List of (pgid, centroid_lat, centroid_lon) tuples.
        """
        ...


@dataclass
class ParityResult:
    """Result of comparing our grid against a reference source."""

    valid: bool
    n_cells_ours: int
    n_cells_reference: int
    n_matched: int = 0
    max_centroid_error_deg: float = 0.0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_parity(
    reader: ReferenceGeometryReader,
    reference_path: Path,
    config: GridConfig | None = None,
    *,
    centroid_tolerance_deg: float = 0.01,
) -> ParityResult:
    """Compare our generated grid against reference data.

    Args:
        reader: An implementation of ReferenceGeometryReader.
        reference_path: Path to the reference shapefile/directory.
        config: Grid config.
        centroid_tolerance_deg: Max allowed centroid deviation in degrees.

    Returns:
        ParityResult with match details.
    """
    from datafactory_grid.generator import generate_grid

    if config is None:
        config = GridConfig()

    # Generate our grid
    pgids, lats, lons = generate_grid(config)
    n_ours = len(pgids)

    # Read reference
    ref_cells = reader.read(reference_path)
    n_ref = len(ref_cells)

    errors: list[str] = []
    warnings: list[str] = []

    if n_ours != n_ref:
        warnings.append(
            f"Cell count mismatch: ours={n_ours}, reference={n_ref}"
        )

    # Build lookup from our grid
    our_lookup = {
        int(pid): (float(lat), float(lon))
        for pid, lat, lon in zip(pgids, lats, lons, strict=True)
    }

    # Compare
    n_matched = 0
    max_error = 0.0

    for ref_id, ref_lat, ref_lon in ref_cells:
        ours = our_lookup.get(ref_id)
        if ours is None:
            if len(errors) < 10:
                errors.append(f"Reference cell {ref_id} not in our grid")
            continue

        our_lat, our_lon = ours
        error = max(abs(our_lat - ref_lat), abs(our_lon - ref_lon))
        max_error = max(max_error, error)

        if error <= centroid_tolerance_deg:
            n_matched += 1
        elif len(errors) < 10:
            errors.append(
                f"Cell {ref_id}: centroid mismatch "
                f"ours=({our_lat:.4f},{our_lon:.4f}) "
                f"ref=({ref_lat:.4f},{ref_lon:.4f}) "
                f"error={error:.4f} deg"
            )

    valid = len(errors) == 0 and n_matched == n_ref

    result = ParityResult(
        valid=valid,
        n_cells_ours=n_ours,
        n_cells_reference=n_ref,
        n_matched=n_matched,
        max_centroid_error_deg=max_error,
        errors=errors,
        warnings=warnings,
    )

    if valid:
        logger.info(
            "Parity PASSED: %d/%d cells matched (max error: %.6f deg)",
            n_matched,
            n_ref,
            max_error,
        )
    else:
        logger.error(
            "Parity FAILED: %d matched, %d errors",
            n_matched,
            len(errors),
        )

    return result


def record_parity_result(
    result: ParityResult,
    ledger_path: Path,
) -> None:
    """Write the parity validation result to provenance.

    Args:
        result: The parity validation result.
        ledger_path: Path to the parity validation JSONL ledger.
    """
    append_ledger_entry(
        ledger_path,
        {
            "valid": result.valid,
            "n_cells_ours": result.n_cells_ours,
            "n_cells_reference": result.n_cells_reference,
            "n_matched": result.n_matched,
            "max_centroid_error_deg": round(result.max_centroid_error_deg, 6),
            "errors": result.errors[:10],
            "warnings": result.warnings,
        },
    )
    logger.info("Parity result recorded to %s", ledger_path)
