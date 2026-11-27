#!/usr/bin/env python3
"""Export the reference tables a consumer needs to interpret the served grid.

The grid publishes ``gaul0_code``, ``gaul1_code`` and ``gaul2_code`` as bare
integers. Nothing served explains them, so a consumer who installs nothing
cannot turn 223 into "Afghanistan". This script writes the keys as files, to
be served beside the grid.

These are *reference data* in Helland's sense: created and managed by one
service and published for others to use. This repository is their custodian,
so it publishes versions rather than shipping a reader (ADR-054, #655).

Format is CSV deliberately, not parquet. These tables are small and their job
is to be readable by anything — a shell script, R, Stata, a spreadsheet — not
to be efficient. The largest is under 300 KB.

Usage:
    uv run python scripts/export_reference_data.py
    uv run python scripts/export_reference_data.py \
        --output-dir /srv/views-data/reference
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

# Where the harvested GAUL per-cell attribute tables live. Each is one row
# per PRIO-GRID cell: (gid, value). Written by scripts/harvest_gaul.py.
DEFAULT_GAUL_DIR = Path("data/raw/gaul_admin")

# -1 is emitted by the grid for cells with no administrative unit — ocean,
# and land GAUL does not cover. A consumer meeting it in the data needs to
# find it in the key rather than guess, so it is exported, not filtered.
NO_UNIT_CODE = -1


def build_country_table(gaul_dir: Path) -> pd.DataFrame:
    """Country code -> name -> ISO3, one row per distinct country.

    ISO3 exists only at country level, which is why this is not folded into
    build_admin_table below. Keeping them apart is clearer than a level
    parameter plus a conditional join.
    """
    code = pd.read_parquet(gaul_dir / "gaul0_code.parquet").rename(
        columns={"value": "gaul0_code"},
    )
    name = pd.read_parquet(gaul_dir / "gaul0_name.parquet").rename(
        columns={"value": "gaul0_name"},
    )
    iso3 = pd.read_parquet(gaul_dir / "iso3_code.parquet").rename(
        columns={"value": "iso3"},
    )
    merged = code.merge(name, on="gid").merge(iso3, on="gid")
    table = merged[["gaul0_code", "gaul0_name", "iso3"]].drop_duplicates()
    return table.sort_values("gaul0_code").reset_index(drop=True)


def build_admin_table(gaul_dir: Path, level: int) -> pd.DataFrame:
    """Admin-level code -> name, one row per distinct unit."""
    code = pd.read_parquet(gaul_dir / f"gaul{level}_code.parquet").rename(
        columns={"value": f"gaul{level}_code"},
    )
    name = pd.read_parquet(gaul_dir / f"gaul{level}_name.parquet").rename(
        columns={"value": f"gaul{level}_name"},
    )
    merged = code.merge(name, on="gid")
    table = merged[
        [f"gaul{level}_code", f"gaul{level}_name"]
    ].drop_duplicates()
    return table.sort_values(f"gaul{level}_code").reset_index(drop=True)


def build_index(written: dict[str, int]) -> dict:
    """Describe what was published, so a consumer can discover it.

    A served file nobody can find is not an interface. This index is the
    entry point: fetch it first, and it names everything else.

    SEAM — second factory. A feature factory serving its own artifacts will
    need either its own index beside this one, or a merged index. Merging
    means agreeing a schema now that neither factory owns alone; a separate
    index means consumers fetch two. Neither is decided. Do not assume this
    file is the only one a consumer will ever read.
    """
    return {
        "description": (
            "Reference tables for interpreting the codes in the VIEWS "
            "data factory grid. Every file here is CSV with a header row."
        ),
        "no_unit_code": NO_UNIT_CODE,
        "no_unit_meaning": (
            "A code of -1 means the cell has no administrative unit — "
            "ocean, or outside GAUL coverage."
        ),
        "files": {
            "gaul0_countries.csv": {
                "columns": ["gaul0_code", "gaul0_name", "iso3"],
                "rows": written["gaul0_countries.csv"],
                "describes": "the gaul0_code feature in the grid",
            },
            "gaul1_admin1.csv": {
                "columns": ["gaul1_code", "gaul1_name"],
                "rows": written["gaul1_admin1.csv"],
                "describes": "the gaul1_code feature in the grid",
            },
            "gaul2_admin2.csv": {
                "columns": ["gaul2_code", "gaul2_name"],
                "rows": written["gaul2_admin2.csv"],
                "describes": "the gaul2_code feature in the grid",
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gaul-dir",
        type=Path,
        default=DEFAULT_GAUL_DIR,
        help=f"harvested GAUL tables (default: {DEFAULT_GAUL_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/reference"),
        help="where to write the CSVs (default: data/reference)",
    )
    args = parser.parse_args()

    if not args.gaul_dir.is_dir():
        print(
            f"ERROR: GAUL directory not found: {args.gaul_dir}\n"
            f"Run scripts/harvest_gaul.py first.",
            file=sys.stderr,
        )
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)

    tables = {
        "gaul0_countries.csv": build_country_table(args.gaul_dir),
        "gaul1_admin1.csv": build_admin_table(args.gaul_dir, 1),
        "gaul2_admin2.csv": build_admin_table(args.gaul_dir, 2),
    }

    written: dict[str, int] = {}
    for filename, table in tables.items():
        path = args.output_dir / filename
        table.to_csv(path, index=False)
        written[filename] = len(table)
        print(f"  {filename:<24} {len(table):>6} rows  {path.stat().st_size:>8} bytes")

    index_path = args.output_dir / "index.json"
    index_path.write_text(json.dumps(build_index(written), indent=2) + "\n")
    print(f"  {'index.json':<24} {'':>6}       {index_path.stat().st_size:>8} bytes")

    print(f"\nWrote {len(tables) + 1} files to {args.output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
