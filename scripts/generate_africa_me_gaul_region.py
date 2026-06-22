#!/usr/bin/env python3
"""Generate the africa_me_gaul bundled region.

Computes africa_me_legacy ∩ land_gaul and writes the result as a
bundled JSON file for datafactory_query.

This region solves the consumer mismatch (#215): africa_me_legacy
contains 5 cells absent from land_gaul, so GAUL-enriching consumers
cannot use africa_me_legacy directly.

Usage:
    uv run python scripts/generate_africa_me_gaul_region.py
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)
logger = logging.getLogger(__name__)

LEGACY_JSON = Path("src/datafactory_query/africa_me_legacy_pgids.json")
LAND_GAUL_JSON = Path("src/datafactory_query/land_gaul_pgids.json")
OUTPUT_JSON = Path("src/datafactory_query/africa_me_gaul_pgids.json")


def main() -> None:
    legacy = set(json.loads(LEGACY_JSON.read_text()))
    land_gaul = set(json.loads(LAND_GAUL_JSON.read_text()))

    logger.info("africa_me_legacy: %d cells", len(legacy))
    logger.info("land_gaul: %d cells", len(land_gaul))

    africa_me_gaul = legacy & land_gaul
    excluded = legacy - land_gaul

    logger.info("africa_me_gaul (intersection): %d cells", len(africa_me_gaul))
    logger.info("Excluded from legacy: %d cells", len(excluded))

    for gid in sorted(excluded):
        logger.info("  excluded gid=%d", gid)

    result = sorted(africa_me_gaul)
    OUTPUT_JSON.write_text(json.dumps(result) + "\n")
    logger.info("Wrote %s (%d cells)", OUTPUT_JSON, len(result))


if __name__ == "__main__":
    main()
