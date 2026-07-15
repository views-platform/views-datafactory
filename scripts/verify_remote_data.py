#!/usr/bin/env python3
"""Post-deploy data correctness verification (C-138).

MANUAL TOOL — retired from the nightly pipeline (2026-07-15, #323).
It compares the remote zarr against the operator's LOCAL assembled
grid, so it false-alarms whenever the local copy is older than the
server's (62 false MISMATCHes on 2026-07-05). Only run it right
after building the local grid from the same inputs as the server.
The nightly path uses scripts/verify_consumer_contract.py instead.

Compares feature sums between the local assembled grid and the
remote zarr store at representative time steps.  Catches the
failure mode from the stale-zarr incident (2026-04-24): a zarr
store can pass all metadata checks while containing wrong values.

Usage:
    uv run python scripts/verify_remote_data.py
    uv run python scripts/verify_remote_data.py --server 204.168.219.108

Requires:
    - Local assembled grid at data/assembled/grid.npy
    - ~/.netrc with server credentials (same as verify_remote.py)
"""

from __future__ import annotations

import argparse
import json
import sys
from netrc import netrc
from pathlib import Path

import numpy as np

from datafactory_query.defaults import DEFAULT_REMOTE

DEFAULT_SERVER = DEFAULT_REMOTE.server
DEFAULT_PORT = 80

LOCAL_GRID = Path("data/assembled/grid.npy")
LOCAL_FEATURES = Path("data/assembled/feature_names.json")


def _result(
    step: str, passed: bool, detail: str,
) -> bool:
    """Print a check result line."""
    label = step.split("]")[0] if "]" in step else step
    dots = "." * max(1, 35 - len(label))
    status = "PASS" if passed else "FAIL"
    print(f"  [{step}] {dots} {status} ({detail})")
    return passed


def _get_credentials(
    server: str,
) -> tuple[str, str] | None:
    netrc_path = Path.home() / ".netrc"
    if not netrc_path.exists():
        return None
    nrc = netrc(str(netrc_path))
    creds = nrc.authenticators(server)
    if creds is None:
        return None
    login, _, password = creds
    return (login, password)


def _select_time_steps(
    n_t: int, grid: np.ndarray, feature_names: list[str],
) -> list[int]:
    """Pick representative time steps: first, middle, last-with-data, last."""
    steps = {0, n_t // 2, n_t - 1}

    ucdp_indices = [
        i for i, name in enumerate(feature_names)
        if name.startswith("ged_")
    ]
    if ucdp_indices:
        ucdp_slice = grid[:, :, :, ucdp_indices]
        has_data = ucdp_slice.sum(axis=(1, 2, 3)) > 0
        valid = np.where(has_data)[0]
        if len(valid) > 0:
            steps.add(int(valid[-1]))

    return sorted(steps)


def main() -> int:
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="Verify remote data correctness (C-138)"
    )
    parser.add_argument(
        "--server", default=DEFAULT_SERVER,
        help=f"Server IP or hostname (default: {DEFAULT_SERVER})",
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT,
        help=f"HTTP port (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--rtol", type=float, default=1e-5,
        help="Relative tolerance for sum comparison (default: 1e-5)",
    )
    args = parser.parse_args()

    server = args.server
    port = args.port
    base_url = f"http://{server}:{port}" if port != 80 else f"http://{server}"
    zarr_url = f"{base_url}/grid.zarr"

    print("=" * 60)
    print("VIEWS Data Factory — Remote Data Verification")
    print(f"Server: {server}:{port}")
    print("=" * 60)
    print()

    n_passed = 0
    n_failed = 0

    step = "1/4  Local grid"
    if not LOCAL_GRID.exists() or not LOCAL_FEATURES.exists():
        _result(step, False, "local grid or feature_names.json missing")
        return 1
    grid = np.load(str(LOCAL_GRID), mmap_mode="r")
    feature_names: list[str] = json.loads(LOCAL_FEATURES.read_text())
    n_t, n_h, n_w, n_f = grid.shape
    ok = _result(
        step, True,
        f"shape {grid.shape}, {n_f} features",
    )
    if ok:
        n_passed += 1
    else:
        n_failed += 1

    step = "2/4  Credentials"
    creds = _get_credentials(server)
    if creds is None:
        _result(step, False, f"no credentials for {server} in ~/.netrc")
        return 1
    ok = _result(step, True, f"user: {creds[0]}")
    if ok:
        n_passed += 1
    else:
        n_failed += 1

    step = "3/4  Remote zarr"
    try:
        import aiohttp
        import xarray as xr

        basic_auth = aiohttp.BasicAuth(creds[0], creds[1])
        ds = xr.open_zarr(
            zarr_url,
            storage_options={
                "client_kwargs": {"auth": basic_auth},
            },
        )
        remote_vars = list(ds.data_vars)
        ok = _result(
            step, True,
            f"{len(remote_vars)} features",
        )
    except Exception as e:
        _result(step, False, str(e))
        return 1
    if ok:
        n_passed += 1
    else:
        n_failed += 1

    step = "4/4  Feature sums"
    time_steps = _select_time_steps(n_t, grid, feature_names)
    print(f"        Comparing {len(time_steps)} time steps: {time_steps}")
    print()

    mismatches = 0
    checked = 0
    for t_idx in time_steps:
        t_pass = 0
        t_fail = 0
        for f_idx, fname in enumerate(feature_names):
            if fname not in remote_vars:
                print(f"    SKIP t={t_idx} {fname}: not in remote store")
                continue

            local_sum = float(np.nansum(grid[t_idx, :, :, f_idx]))
            remote_slice = ds[fname].isel(time=t_idx).values
            remote_sum = float(np.nansum(remote_slice))

            if local_sum == 0.0 and remote_sum == 0.0:
                t_pass += 1
                checked += 1
                continue

            denom = max(abs(local_sum), abs(remote_sum), 1e-12)
            rel_diff = abs(local_sum - remote_sum) / denom

            if rel_diff > args.rtol:
                print(
                    f"    MISMATCH t={t_idx} {fname}: "
                    f"local={local_sum:.4f}, "
                    f"remote={remote_sum:.4f}, "
                    f"rel_diff={rel_diff:.2e}"
                )
                t_fail += 1
                mismatches += 1
            else:
                t_pass += 1
            checked += 1

        label = f"  t={t_idx}"
        dots = "." * max(1, 35 - len(label))
        if t_fail > 0:
            print(f"  [{label}] {dots} FAIL ({t_fail} mismatches)")
            n_failed += 1
        else:
            print(f"  [{label}] {dots} PASS ({t_pass} features match)")
            n_passed += 1

    ds.close()

    print()
    print("=" * 60)
    if mismatches == 0:
        print(
            f"ALL CHECKS PASSED "
            f"({checked} comparisons across "
            f"{len(time_steps)} time steps)"
        )
    else:
        print(
            f"{mismatches} MISMATCHES "
            f"({checked} comparisons across "
            f"{len(time_steps)} time steps)"
        )
    print("=" * 60)

    return 0 if mismatches == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
