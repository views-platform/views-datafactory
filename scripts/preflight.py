#!/usr/bin/env python3
"""Pre-flight checks — run before the pipeline starts.

Usage:
    uv run python scripts/preflight.py
    uv run python scripts/preflight.py --data-dir data

Validates that all prerequisites are met before the 30-minute
pipeline begins: source credentials, zarr server credentials,
and disk space.
Exits 0 if all pass, 1 if any fail.

Called by refresh_pipeline.sh as step 0 (before harvest).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from netrc import netrc
from pathlib import Path

from datafactory_provenance.source_registry import (
    PIPELINE_SOURCES,
    validate_preflight,
)
from datafactory_query.defaults import DEFAULT_REMOTE

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

    # Zarr server credentials (needed by step 12: verify_remote_data.py)
    server = DEFAULT_REMOTE.server
    netrc_path = Path.home() / ".netrc"
    if not netrc_path.exists():
        print(
            f"  {'Zarr server (~/.netrc)':35s} FAIL  "
            f"~/.netrc not found"
        )
        any_fail = True
    else:
        try:
            nrc = netrc(str(netrc_path))
            creds = nrc.authenticators(server)
            if creds is None:
                print(
                    f"  {'Zarr server (~/.netrc)':35s} FAIL  "
                    f"no entry for {server}"
                )
                any_fail = True
            else:
                import requests

                zarr_url = f"http://{server}/grid.zarr/.zmetadata"
                try:
                    resp = requests.head(
                        zarr_url,
                        auth=(creds[0], creds[2] or ""),
                        timeout=10,
                    )
                    if resp.status_code == 401:
                        print(
                            f"  {'Zarr server (~/.netrc)':35s} FAIL  "
                            f"credentials rejected (401) for {server}"
                        )
                        any_fail = True
                    elif resp.status_code < 400:
                        print(
                            f"  {'Zarr server (~/.netrc)':35s} OK    "
                            f"authenticated as {creds[0]}"
                        )
                    else:
                        print(
                            f"  {'Zarr server (~/.netrc)':35s} WARN  "
                            f"HTTP {resp.status_code} (credentials present, "
                            f"server may be down)"
                        )
                except requests.ConnectionError:
                    print(
                        f"  {'Zarr server (~/.netrc)':35s} WARN  "
                        f"cannot reach {server} (credentials present, "
                        f"will retry at step 12)"
                    )
                except requests.Timeout:
                    print(
                        f"  {'Zarr server (~/.netrc)':35s} WARN  "
                        f"timeout reaching {server} (credentials present, "
                        f"will retry at step 12)"
                    )
        except Exception as e:
            print(
                f"  {'Zarr server (~/.netrc)':35s} FAIL  "
                f"{e}"
            )
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
