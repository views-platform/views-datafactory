"""Generate the land_gaul bundled region (land ∩ GAUL coverage).

Reads:
  - src/datafactory_query/land_pgids.json  (64,818 land cells)
  - data/raw/gaul_admin/gaul0_code.parquet (area-majority assignments)

Writes:
  - src/datafactory_query/land_gaul_pgids.json  (sorted int array)
  - Provenance ledger entry

The 82 excluded cells are sub-Antarctic islands outside FAO GAUL 2024
coverage. They are printed with coordinates for the FAO release note.

Related: issue #159, ADR-039 (spatial truth ownership).
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

from datafactory_priogrid import pgid_to_latlon
from datafactory_provenance import (
    DIGEST_SCHEME,
    LEDGER_VERSION,
    append_ledger_entry,
    compute_content_digest,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)
logger = logging.getLogger(__name__)

DATASET_ID = "land_gaul_region"


def generate(
    land_json: Path,
    gaul_parquet: Path,
    output_json: Path,
    ledger_path: Path,
) -> dict:
    """Compute land ∩ GAUL and write the bundled JSON."""
    land_pgids = set(json.loads(land_json.read_text()))
    logger.info("Land cells: %d", len(land_pgids))

    table = pq.read_table(gaul_parquet)
    gids = table.column("gid").to_pylist()
    codes = table.column("value").to_pylist()
    gaul_valid = {gid for gid, code in zip(gids, codes, strict=True) if code != -1}
    logger.info("GAUL-assigned cells (code != -1): %d", len(gaul_valid))

    land_gaul = sorted(land_pgids & gaul_valid)
    excluded = sorted(land_pgids - gaul_valid)

    logger.info("land_gaul (intersection): %d", len(land_gaul))
    logger.info("Excluded (land without GAUL): %d", len(excluded))

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(land_gaul))

    content_digest = compute_content_digest(
        json.dumps(land_gaul).encode()
    )

    land_digest = compute_content_digest(land_json.read_bytes())
    gaul_digest = compute_content_digest(gaul_parquet.read_bytes())

    append_ledger_entry(ledger_path, {
        "dataset": DATASET_ID,
        "version": "v1",
        "method": "land_intersection_gaul0",
        "n_land": len(land_pgids),
        "n_gaul_valid": len(gaul_valid),
        "n_land_gaul": len(land_gaul),
        "n_excluded": len(excluded),
        "content_digest": content_digest,
        "source_land_digest": land_digest,
        "source_gaul_digest": gaul_digest,
        "digest_algorithm": DIGEST_SCHEME,
        "ledger_version": LEDGER_VERSION,
    })

    lats, lons = pgid_to_latlon(np.array(excluded))
    print(f"\n{'='*60}")
    print(f"Excluded cells ({len(excluded)} land cells without GAUL code):")
    print(f"{'='*60}")
    for gid, lat, lon in zip(excluded, lats.tolist(), lons.tolist(), strict=True):
        print(f"  gid={gid:<8d}  lat={lat:7.2f}  lon={lon:7.2f}")
    print(f"{'='*60}\n")

    return {
        "n_land": len(land_pgids),
        "n_land_gaul": len(land_gaul),
        "n_excluded": len(excluded),
        "digest": content_digest,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--land-json",
        type=Path,
        default=Path("src/datafactory_query/land_pgids.json"),
    )
    parser.add_argument(
        "--gaul-parquet",
        type=Path,
        default=Path("data/raw/gaul_admin/gaul0_code.parquet"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("src/datafactory_query/land_gaul_pgids.json"),
    )
    parser.add_argument(
        "--ledger-path",
        type=Path,
        default=Path("provenance/gaul_admin/ingestion_ledger.jsonl"),
    )
    args = parser.parse_args()

    result = generate(
        land_json=args.land_json,
        gaul_parquet=args.gaul_parquet,
        output_json=args.output,
        ledger_path=args.ledger_path,
    )

    logger.info(
        "Done: %d land_gaul cells (%d excluded), digest=%s",
        result["n_land_gaul"],
        result["n_excluded"],
        result["digest"],
    )


if __name__ == "__main__":
    main()
