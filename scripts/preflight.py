#!/usr/bin/env python3
"""Pre-flight checks — run before the pipeline starts.

Usage:
    uv run python scripts/preflight.py
    uv run python scripts/preflight.py --data-dir data

Validates that all prerequisites are met before the 30-minute
pipeline begins: credentials and disk space.
Exits 0 if all pass, 1 if any fail.

Called by refresh_pipeline.sh as step 0 (before harvest).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from datafactory_provenance.source_registry import (
    PIPELINE_SOURCES,
    validate_preflight,
)

MIN_DISK_GB = 40


def main() -> int:
    """Run pre-flight checks."""
    parser = argparse.ArgumentParser(
        description="Pre-flight pipeline checks"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Base data directory (for disk space check)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Pre-flight checks")
    print("=" * 60)

    any_fail = False

    # Credential checks
    results = validate_preflight(PIPELINE_SOURCES)
    for r in results:
        mark = "OK" if r["status"] == "OK" else "FAIL"
        src = r.get("source", "")
        label = f"{r['name']} ({src})" if src else r["name"]
        print(f"  {label:35s} {mark:4s}  {r['detail']}")
        if r["status"] != "OK":
            any_fail = True

    # Disk space check
    check_dir = args.data_dir if args.data_dir.exists() else Path(".")
    free = shutil.disk_usage(check_dir).free
    free_gb = free / (1024**3)
    if free_gb < MIN_DISK_GB:
        print(
            f"  {'Disk space':35s} FAIL  "
            f"{free_gb:.0f} GB free (need {MIN_DISK_GB} GB)"
        )
        any_fail = True
    else:
        print(
            f"  {'Disk space':35s} OK    "
            f"{free_gb:.0f} GB free"
        )

    print()

    if any_fail:
        print("FATAL: pre-flight checks failed")
        return 1

    print("All pre-flight checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
