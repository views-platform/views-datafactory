"""PRIO-GRID static features harvester.

Fetches static variables (terrain, resources, land cover) from the
PRIO-GRID 2.0 API (https://grid.prio.org/api). These are frozen
datasets (2009-2015 vintages) covering 64,818 land cells.

Each variable is stored as a separate Parquet file with columns
(gid, value). Provenance is tracked per variable.

This is the second data source in the datafactory (after UCDP).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import requests

from datafactory_harvester.snapshot_storage import archive_snapshot
from datafactory_harvester.sources import register_source
from datafactory_provenance import (
    DIGEST_SCHEME,
    LEDGER_VERSION,
    append_ledger_entry,
    compute_content_digest,
    last_digest_for_version,
)

logger = logging.getLogger(__name__)

DATASET_ID = "priogrid_static"
PRIOGRID_API_URL = "https://grid.prio.org/api"

# ---- Boundary declarations (ADR-009) ----
REQUIRED_CELL_FIELDS: set[str] = {"gid", "value"}


# ---- Config ----


@dataclass(frozen=True)
class PriogridStaticConfig:
    """Configuration for fetching PRIO-GRID static features.

    Static variables are frozen snapshots (terrain, resources,
    land cover). They change only when PRIO releases a new
    version of the grid, which is rare.
    """

    api_url: str = PRIOGRID_API_URL
    data_dir: Path = Path("data/raw/priogrid_static")
    ledger_path: Path = Path(
        "provenance/priogrid_static/ingestion_ledger.jsonl"
    )
    timeout: int = 60
    variables: tuple[str, ...] | None = field(default=None)

    def __post_init__(self) -> None:
        if self.timeout < 1:
            err_msg = (
                f"timeout must be >= 1, got {self.timeout}"
            )
            logger.error(err_msg)
            raise ValueError(err_msg)


# ---- Helpers ----


def _discover_static_variables(
    api_url: str, timeout: int
) -> list[dict]:
    """Fetch the variable catalog and return static variables."""
    resp = requests.get(
        f"{api_url}/variables", timeout=timeout
    )
    resp.raise_for_status()
    all_vars = resp.json()
    return [v for v in all_vars if v.get("type") == "static"]


def _snapshot_path(
    config: PriogridStaticConfig, variable_name: str
) -> Path:
    """Build the Parquet snapshot path for a variable."""
    return config.data_dir / f"{variable_name}.parquet"


def _fetch_variable(
    config: PriogridStaticConfig,
    variable: dict,
    *,
    force_refresh: bool = False,
) -> dict:
    """Fetch a single static variable.

    Local-first: if Parquet exists and ledger has digest, skip.

    Returns a result dict with variable name, outcome, and
    cell count.
    """
    name = variable["name"]
    snap_path = _snapshot_path(config, name)

    # Local-first skip
    if not force_refresh and snap_path.exists():
        previous = last_digest_for_version(
            config.ledger_path, name
        )
        if previous is not None:
            logger.info(
                "Variable %s already on disk (digest: %s)",
                name, previous,
            )
            return {
                "variable": name,
                "outcome": "cached",
                "digest": previous,
            }

    # Fetch from API
    t0 = time.monotonic()
    resp = requests.get(
        f"{config.api_url}/data/{name}",
        timeout=config.timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    fetch_duration = time.monotonic() - t0

    cells = data.get("cells", [])
    if not cells:
        err_msg = f"Variable {name} returned 0 cells"
        logger.error(err_msg)
        append_ledger_entry(config.ledger_path, {
            "dataset": DATASET_ID,
            "version": name,
            "n_cells": 0,
            "outcome": "failed",
            "errors": [err_msg],
            "ledger_version": LEDGER_VERSION,
            "digest_algorithm": DIGEST_SCHEME,
        })
        return {
            "variable": name,
            "outcome": "failed",
            "errors": [err_msg],
        }

    # Validate required fields on first cell
    first = cells[0]
    missing = REQUIRED_CELL_FIELDS - set(first.keys())
    if missing:
        err_msg = (
            f"Variable {name}: cells missing fields "
            f"{sorted(missing)}"
        )
        logger.error(err_msg)
        return {
            "variable": name,
            "outcome": "failed",
            "errors": [err_msg],
        }

    # Type validation (warnings, not errors)
    warnings: list[str] = []
    n_type_errors = 0
    for c in cells:
        if not isinstance(c.get("gid"), (int, float)):
            n_type_errors += 1
        if not isinstance(c.get("value"), (int, float)):
            n_type_errors += 1
    if n_type_errors > 0:
        warnings.append(
            f"{n_type_errors} type violations in "
            f"{len(cells)} cells"
        )

    # Check gid uniqueness
    gid_list = [c["gid"] for c in cells]
    unique_gids = set(gid_list)
    if len(unique_gids) != len(gid_list):
        n_dupes = len(gid_list) - len(unique_gids)
        warnings.append(
            f"Duplicate gids: {n_dupes} duplicates "
            f"in {len(gid_list)} cells"
        )

    # Build Parquet table
    gids = gid_list
    values = [c["value"] for c in cells]
    table = pa.table({
        "gid": pa.array(gids, type=pa.int32()),
        "value": pa.array(values, type=pa.float64()),
    })

    # Compute digest
    content_bytes = json.dumps(
        sorted((c["gid"], c["value"]) for c in cells),
        sort_keys=True,
    ).encode()
    content_digest = compute_content_digest(content_bytes)

    # Check if unchanged
    previous = last_digest_for_version(
        config.ledger_path, name
    )
    if previous == content_digest and not force_refresh:
        logger.info(
            "Variable %s unchanged (digest: %s)",
            name, content_digest,
        )
        append_ledger_entry(config.ledger_path, {
            "dataset": DATASET_ID,
            "version": name,
            "n_cells": len(cells),
            "content_digest": content_digest,
            "warnings": warnings,
            "outcome": "unchanged",
            "ledger_version": LEDGER_VERSION,
            "digest_algorithm": DIGEST_SCHEME,
        })
        return {
            "variable": name,
            "outcome": "unchanged",
            "digest": content_digest,
        }

    # Archive old snapshot before overwriting (P4)
    if snap_path.exists():
        archive_snapshot(snap_path)
        logger.info(
            "Archived previous %s snapshot", name,
        )

    # Store
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, snap_path, compression="snappy")

    # Variable metadata for provenance
    var_meta = {
        "display_name": variable.get("displayName", ""),
        "category": variable.get("category", ""),
        "unit": variable.get("unit", ""),
        "source_name": variable.get("sourceName", ""),
    }

    # Provenance
    append_ledger_entry(config.ledger_path, {
        "dataset": DATASET_ID,
        "version": name,
        "n_cells": len(cells),
        "min_value": data.get("minValue"),
        "max_value": data.get("maxValue"),
        "fetch_duration_s": round(fetch_duration, 2),
        "content_digest": content_digest,
        "variable_metadata": var_meta,
        "warnings": warnings,
        "outcome": "success",
        "ledger_version": LEDGER_VERSION,
        "digest_algorithm": DIGEST_SCHEME,
    })

    logger.info(
        "Fetched %s: %d cells, digest %s (%.1fs)",
        name, len(cells), content_digest, fetch_duration,
    )

    return {
        "variable": name,
        "outcome": "success",
        "n_cells": len(cells),
        "digest": content_digest,
        "path": str(snap_path),
    }


# ---- Orchestrator ----


def fetch_priogrid_static(
    config: PriogridStaticConfig | None = None,
    *,
    force_refresh: bool = False,
) -> list[dict]:
    """Fetch PRIO-GRID static variables.

    Discovers available static variables from the API catalog,
    fetches each one, validates, and stores as Parquet with
    provenance tracking.

    Args:
        config: Harvest configuration. Uses defaults if None.
        force_refresh: If True, re-fetch even if cached.

    Returns:
        List of per-variable result dicts with outcome.
    """
    if config is None:
        config = PriogridStaticConfig()

    # Discover static variables
    all_static = _discover_static_variables(
        config.api_url, config.timeout
    )
    logger.info(
        "Discovered %d static variables", len(all_static)
    )

    # Filter to requested subset if specified
    if config.variables is not None:
        requested = set(config.variables)
        filtered = [
            v for v in all_static
            if v["name"] in requested
        ]
        missing = requested - {v["name"] for v in filtered}
        if missing:
            logger.warning(
                "Requested variables not found: %s",
                sorted(missing),
            )
        all_static = filtered

    # Fetch each variable
    results = []
    for i, variable in enumerate(all_static, 1):
        name = variable["name"]
        logger.info(
            "Fetching %s (%d/%d)...",
            name, i, len(all_static),
        )
        try:
            result = _fetch_variable(
                config, variable,
                force_refresh=force_refresh,
            )
            results.append(result)
        except (
            requests.RequestException,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            logger.error(
                "Failed to fetch %s: %s", name, exc
            )
            results.append({
                "variable": name,
                "outcome": "failed",
                "errors": [str(exc)],
            })

    return results


# Auto-register
register_source("priogrid_static", fetch_priogrid_static)
