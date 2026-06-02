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

import requests

from datafactory_provenance.source_registry import (
    PIPELINE_SOURCES,
    validate_preflight,
)
from datafactory_query.defaults import DEFAULT_REMOTE

MIN_DISK_GB = 40


def _check_zarr_credentials(server: str) -> dict:
    """Validate zarr server credentials from ~/.netrc via HTTP HEAD."""
    name = "Zarr server (~/.netrc)"
    netrc_path = Path.home() / ".netrc"
    if not netrc_path.exists():
        return {"name": name, "status": "FAIL", "detail": "~/.netrc not found"}

    try:
        nrc = netrc(str(netrc_path))
        creds = nrc.authenticators(server)
    except Exception as e:
        return {"name": name, "status": "FAIL", "detail": str(e)}

    if creds is None:
        return {"name": name, "status": "FAIL", "detail": f"no entry for {server}"}

    zarr_url = f"http://{server}/grid.zarr/.zmetadata"
    try:
        resp = requests.head(
            zarr_url,
            auth=(creds[0], creds[2] or ""),
            timeout=10,
        )
    except requests.ConnectionError:
        return {
            "name": name,
            "status": "WARN",
            "detail": f"cannot reach {server} (credentials present, "
            f"will retry at step 12)",
        }
    except requests.Timeout:
        return {
            "name": name,
            "status": "WARN",
            "detail": f"timeout reaching {server} (credentials present, "
            f"will retry at step 12)",
        }

    if resp.status_code == 401:
        return {
            "name": name,
            "status": "FAIL",
            "detail": f"credentials rejected (401) for {server}",
        }
    if resp.status_code < 400:
        return {
            "name": name,
            "status": "OK",
            "detail": f"authenticated as {creds[0]}",
        }
    return {
        "name": name,
        "status": "WARN",
        "detail": f"HTTP {resp.status_code} (credentials present, "
        f"server may be down)",
    }


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
    r = _check_zarr_credentials(DEFAULT_REMOTE.server)
    mark = "OK" if r["status"] == "OK" else r["status"]
    print(f"  {r['name']:35s} {mark:4s}  {r['detail']}")
    if r["status"] == "FAIL":
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
