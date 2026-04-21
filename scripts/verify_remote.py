#!/usr/bin/env python3
"""Verify the Hetzner data server is serving data correctly.

Usage:
    uv run python scripts/verify_remote.py
    uv run python scripts/verify_remote.py --server 204.168.219.108

Runs 10 checks against the remote server: connectivity, auth,
metadata, dimensions, variables, data access, and sanity.

Requires ~/.netrc with server credentials (one-time setup):

    machine 204.168.219.108
    login views
    password yourpassword

    chmod 600 ~/.netrc

All checks (including xarray) read from ~/.netrc. The xarray
check wraps credentials in aiohttp.BasicAuth as required by
fsspec's HTTP backend (see C-96).

See docs/guides/hetzner_deployment_guide.md Phase 5 for details.
"""

from __future__ import annotations

import argparse
import socket
import sys
from datetime import datetime, timezone
from netrc import netrc
from pathlib import Path

import requests

from datafactory_priogrid.grid_config import DEFAULT_GRID_CONFIG
from datafactory_query.defaults import DEFAULT_REMOTE

DEFAULT_SERVER = DEFAULT_REMOTE.server
DEFAULT_PORT = 80

EXPECTED_N_FEATURES = 43
EXPECTED_N_TIME = 456
EXPECTED_N_LAT = DEFAULT_GRID_CONFIG.nrow
EXPECTED_N_LON = DEFAULT_GRID_CONFIG.ncol
EXPECTED_CRS = "EPSG:4326"
EXPECTED_RESOLUTION = DEFAULT_GRID_CONFIG.resolution
EXPECTED_SOURCE = "views-datafactory"

EXPECTED_UCDP = {
    "ged_sb_count", "ged_sb_best",
    "ged_ns_count", "ged_ns_best",
    "ged_os_count", "ged_os_best",
}
EXPECTED_ADMIN = {"gaul0_code", "gaul1_code", "gaul2_code"}
EXPECTED_STATIC = {
    "agri_gc", "aquaveg_gc", "barren_gc",
    "cmr_max", "cmr_mean", "cmr_min", "cmr_sd",
    "diamprim_s", "diamsec_s",
    "forest_gc", "gem_s",
    "goldplacer_s", "goldsurface_s", "goldvein_s",
    "growend", "growstart", "harvarea",
    "herb_gc",
    "imr_max", "imr_mean", "imr_min", "imr_sd",
    "landarea", "maincrop", "mountains_mean",
    "petroleum_s", "rainseas",
    "shrub_gc",
    "ttime_max", "ttime_mean", "ttime_min", "ttime_sd",
    "urban_gc", "water_gc",
}


def _result(
    step: str, passed: bool, detail: str,
) -> bool:
    """Print a check result line."""
    label = step.split("]")[0] if "]" in step else step
    dots = "." * max(1, 35 - len(label))
    status = "PASS" if passed else "FAIL"
    print(f"  [{step}] {dots} {status} ({detail})")
    return passed


def main() -> int:
    """Run remote verification checks."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="Verify VIEWS data server (remote)"
    )
    parser.add_argument(
        "--server",
        default=DEFAULT_SERVER,
        help=f"Server IP or hostname (default: {DEFAULT_SERVER})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"HTTP port (default: {DEFAULT_PORT})",
    )
    args = parser.parse_args()

    server = args.server
    port = args.port
    base_url = f"http://{server}:{port}" if port != 80 else f"http://{server}"
    zarr_url = f"{base_url}/grid.zarr"
    parquet_url = f"{base_url}/dataframe.parquet"
    n_passed = 0
    n_failed = 0

    print("=" * 60)
    print("VIEWS Data Factory — Remote Verification")
    print(f"Server: {server}:{port}")
    print("=" * 60)
    print()

    # ---- Check 1: Connectivity ----
    step = " 1/10  Connectivity"
    try:
        sock = socket.create_connection((server, port), timeout=10)
        sock.close()
        ok = _result(step, True, f"HTTP {port} reachable")
    except (OSError, TimeoutError) as e:
        ok = _result(step, False, f"cannot connect: {e}")
    if ok:
        n_passed += 1
    else:
        n_failed += 1
        print("  STOP: Server unreachable. Remaining checks skipped.")
        return 1

    # ---- Check 2: Auth enforcement ----
    # Use a fresh Session with trust_env=False to prevent
    # auto-reading ~/.netrc credentials for this test.
    step = " 2/10  Auth enforcement"
    try:
        no_auth = requests.Session()
        no_auth.trust_env = False
        resp = no_auth.get(
            f"{zarr_url}/.zmetadata", timeout=10,
        )
        if resp.status_code == 401:
            ok = _result(step, True, "401 without credentials")
        else:
            ok = _result(step, False, f"expected 401, got {resp.status_code}")
    except requests.RequestException as e:
        ok = _result(step, False, str(e))
    if ok:
        n_passed += 1
    else:
        n_failed += 1

    # ---- Check 3: Netrc credentials ----
    step = " 3/10  Netrc credentials"
    auth_tuple = None
    try:
        netrc_path = Path.home() / ".netrc"
        if not netrc_path.exists():
            ok = _result(step, False, "~/.netrc not found")
            print()
            print("  Setup instructions:")
            print(f"    echo 'machine {server}' >> ~/.netrc")
            print("    echo 'login views' >> ~/.netrc")
            print("    echo 'password YOUR_PASSWORD' >> ~/.netrc")
            print("    chmod 600 ~/.netrc")
            print()
        else:
            nrc = netrc(str(netrc_path))
            creds = nrc.authenticators(server)
            if creds is None:
                ok = _result(step, False, f"no entry for {server} in ~/.netrc")
                print()
                print("  Add to ~/.netrc:")
                print(f"    machine {server}")
                print("    login views")
                print("    password YOUR_PASSWORD")
                print()
            else:
                login, _, password = creds
                auth_tuple = (login, password)
                ok = _result(step, True, f"user: {login}")
    except Exception as e:
        ok = _result(step, False, str(e))
    if ok:
        n_passed += 1
    else:
        n_failed += 1
        print("  STOP: No credentials. Remaining checks require auth.")
        return 1

    # ---- Check 4: Metadata ----
    step = " 4/10  Metadata"
    metadata = None
    try:
        resp = requests.get(
            f"{zarr_url}/.zmetadata",
            auth=auth_tuple,
            timeout=30,
        )
        resp.raise_for_status()
        metadata = resp.json()
        meta_keys = metadata.get("metadata", {})
        # Count data variables (entries with .zarray that aren't coordinates)
        data_vars = [
            k.split("/")[0]
            for k in meta_keys
            if k.endswith("/.zarray")
            and k.split("/")[0] not in ("time", "lat", "lon", "pgid")
        ]
        n_vars = len(data_vars)
        ok = _result(step, True, f".zmetadata: {n_vars} features")
    except Exception as e:
        ok = _result(step, False, str(e))
    if ok:
        n_passed += 1
    else:
        n_failed += 1

    # ---- Check 5: Dataset attributes ----
    step = " 5/10  Dataset attributes"
    if metadata:
        try:
            attrs = metadata["metadata"][".zattrs"]
            checks = []
            if attrs.get("crs") != EXPECTED_CRS:
                checks.append(f"crs={attrs.get('crs')}")
            if attrs.get("resolution_degrees") != EXPECTED_RESOLUTION:
                checks.append(f"res={attrs.get('resolution_degrees')}")
            if attrs.get("source") != EXPECTED_SOURCE:
                checks.append(f"source={attrs.get('source')}")
            if attrs.get("n_features") != EXPECTED_N_FEATURES:
                checks.append(f"n_features={attrs.get('n_features')}")
            ts = attrs.get("export_timestamp")
            if not ts:
                checks.append("export_timestamp missing (D-03)")
            if checks:
                ok = _result(step, False, f"mismatches: {', '.join(checks)}")
            else:
                age_str = ""
                try:
                    ts_dt = datetime.fromisoformat(ts)
                    now = datetime.now(tz=timezone.utc)
                    age_h = (now - ts_dt).total_seconds() / 3600
                    if age_h < 48:
                        age_str = f", age {age_h:.0f}h"
                    else:
                        age_str = f", age {age_h / 24:.0f}d"
                    if age_h >= 168:
                        age_str += " (SLO BREACH >168h)"
                except (ValueError, TypeError):
                    pass
                ok = _result(
                    step, True,
                    f"{EXPECTED_CRS}, {EXPECTED_RESOLUTION}°,"
                    f" exported {ts[:10]}{age_str}",
                )
        except KeyError as e:
            ok = _result(step, False, f"missing key: {e}")
    else:
        ok = _result(step, False, "no metadata to check")
    if ok:
        n_passed += 1
    else:
        n_failed += 1

    # ---- Check 6: Dimensions ----
    step = " 6/10  Dimensions"
    if metadata:
        try:
            meta = metadata["metadata"]
            sb_zarray = meta.get("ged_sb_best/.zarray", {})
            shape = sb_zarray.get("shape", [])

            problems = []
            if len(shape) != 3:
                problems.append(f"expected 3D, got {len(shape)}D")
            else:
                if shape[0] != EXPECTED_N_TIME:
                    problems.append(f"time={shape[0]}, expected {EXPECTED_N_TIME}")
                if shape[1] != EXPECTED_N_LAT:
                    problems.append(f"lat={shape[1]}, expected {EXPECTED_N_LAT}")
                if shape[2] != EXPECTED_N_LON:
                    problems.append(f"lon={shape[2]}, expected {EXPECTED_N_LON}")

            if problems:
                ok = _result(step, False, "; ".join(problems))
            else:
                ok = _result(
                    step, True,
                    f"{shape[0]} months, {shape[1]} lat, {shape[2]} lon",
                )
        except Exception as e:
            ok = _result(step, False, str(e))
    else:
        ok = _result(step, False, "no metadata to check")
    if ok:
        n_passed += 1
    else:
        n_failed += 1

    # ---- Check 7: Variables ----
    step = " 7/10  Variables"
    if metadata:
        try:
            meta_keys = metadata.get("metadata", {})
            found_vars = {
                k.split("/")[0]
                for k in meta_keys
                if k.endswith("/.zarray")
                and k.split("/")[0] not in ("time", "lat", "lon", "pgid")
            }
            missing_ucdp = EXPECTED_UCDP - found_vars
            missing_static = EXPECTED_STATIC - found_vars
            missing_admin = EXPECTED_ADMIN - found_vars
            n_ucdp = len(EXPECTED_UCDP & found_vars)
            n_static = len(EXPECTED_STATIC & found_vars)
            n_admin = len(EXPECTED_ADMIN & found_vars)

            all_missing = missing_ucdp | missing_static | missing_admin
            if all_missing:
                ok = _result(step, False, f"missing: {sorted(all_missing)}")
            else:
                ok = _result(
                    step, True,
                    f"{n_ucdp} UCDP + {n_static} static"
                    f" + {n_admin} admin = {len(found_vars)}",
                )
        except Exception as e:
            ok = _result(step, False, str(e))
    else:
        ok = _result(step, False, "no metadata to check")
    if ok:
        n_passed += 1
    else:
        n_failed += 1

    # ---- Check 8: Data access (xarray) ----
    # Reads netrc credentials and wraps them in aiohttp.BasicAuth
    # (required by fsspec's aiohttp backend — C-96).
    step = " 8/10  Data access"
    ds = None
    try:
        import aiohttp
        import xarray as xr

        basic_auth = aiohttp.BasicAuth(
            auth_tuple[0], auth_tuple[1],
        )
        ds = xr.open_zarr(
            zarr_url,
            storage_options={
                "client_kwargs": {"auth": basic_auth},
            },
        )
        # Load a single chunk to verify actual data transfer
        chunk = ds["ged_sb_best"].isel(time=slice(0, 12)).values
        ok = _result(
            step, True,
            f"xarray loaded 1 chunk: "
            f"{chunk.shape[0]}x{chunk.shape[1]}x{chunk.shape[2]}",
        )
    except ImportError:
        ok = _result(step, False, "xarray not installed")
    except Exception as e:
        ok = _result(step, False, str(e))
    if ok:
        n_passed += 1
    else:
        n_failed += 1

    # ---- Check 9: Data sanity ----
    step = " 9/10  Data sanity"
    if ds is not None:
        try:
            import numpy as np

            sb_best = ds["ged_sb_best"].values
            total_fatalities = float(np.nansum(sb_best))
            n_nonzero = int(np.count_nonzero(~np.isnan(sb_best) & (sb_best > 0)))

            if total_fatalities <= 0:
                ok = _result(step, False, "ged_sb_best sum is zero or negative")
            elif n_nonzero == 0:
                ok = _result(step, False, "ged_sb_best has no non-zero values")
            else:
                if total_fatalities > 1e6:
                    magnitude = f"{total_fatalities / 1e6:.1f}M"
                else:
                    magnitude = f"{total_fatalities:.0f}"
                ok = _result(
                    step, True,
                    f"ged_sb_best total: ~{magnitude}, {n_nonzero:,} non-zero cells",
                )
        except Exception as e:
            ok = _result(step, False, str(e))
    else:
        ok = _result(step, False, "no dataset to check")
    if ok:
        n_passed += 1
    else:
        n_failed += 1

    # ---- Check 10: Parquet ----
    step = "10/10  Parquet"
    try:
        resp = requests.head(
            parquet_url,
            auth=auth_tuple,
            timeout=30,
        )
        if resp.status_code == 200:
            size_mb = int(resp.headers.get("content-length", 0)) / 1e6
            ok = _result(
                step, True,
                f"dataframe.parquet available ({size_mb:.0f} MB)",
            )
        else:
            ok = _result(step, False, f"HTTP {resp.status_code}")
    except Exception as e:
        ok = _result(step, False, str(e))
    if ok:
        n_passed += 1
    else:
        n_failed += 1

    # ---- Summary ----
    print()
    print("=" * 60)
    if n_failed == 0:
        print(f"ALL {n_passed} CHECKS PASSED")
    else:
        print(f"{n_passed} passed, {n_failed} failed")
    print("=" * 60)

    return 0 if n_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
