"""Land mask — identify land cells from the PRIO-GRID API.

The PRIO-GRID API (https://grid.prio.org) returns data only for
land cells. The ``landarea`` variable contains 64,818 cells — each
with landarea > 0. Ocean cells are not in the API responses.

Results are cached to disk to avoid re-fetching.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_PRIOGRID_API_URL = "https://grid.prio.org/api/data/landarea"
_DEFAULT_CACHE_PATH = Path("data/raw/priogrid/land_pgids.json")


def fetch_land_pgids(
    *,
    cache_path: Path = _DEFAULT_CACHE_PATH,
    force_refresh: bool = False,
) -> set[int]:
    """Return the set of PRIO-GRID cell IDs that are land.

    Fetches the ``landarea`` variable from the PRIO-GRID API,
    which returns only cells with land area > 0 (64,818 cells).
    Results are cached to disk as JSON.

    Args:
        cache_path: Where to cache the land pgid list.
        force_refresh: If True, re-fetch even if cache exists.

    Returns:
        Set of integer pgids representing land cells.
    """
    if not force_refresh and cache_path.exists():
        pgids = json.loads(cache_path.read_text())
        logger.info(
            "Loaded %d land pgids from cache: %s",
            len(pgids), cache_path,
        )
        return set(pgids)

    logger.info("Fetching land pgids from PRIO-GRID API...")
    resp = requests.get(_PRIOGRID_API_URL, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    pgids = sorted(c["gid"] for c in data["cells"])

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(pgids))
    logger.info(
        "Fetched %d land pgids, cached to %s",
        len(pgids), cache_path,
    )
    return set(pgids)
