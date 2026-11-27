#!/usr/bin/env python3
"""Stamp build identity onto a zarr store that already exists.

``export_zarr.py`` records which release produced a store as it writes it.
That is the trustworthy path, and it only happens on an export. The monthly
pipeline exports on the 21st, so a store built before this feature existed
carries no identity until then.

This script adds it to a store in place, without re-exporting — a five-hour
operation that would also replace the data consumers are currently reading.

The result is marked ``build_identity_source: "stamped"`` rather than
``"export"``, because it asserts a link this run did not observe: it reports
the checkout as it is *now*, not necessarily the one that built the store.
A consumer can tell the two apart, which is the point of recording it.

Safe to run against a live store: ``.zattrs`` gains keys and loses none.
Every reader in this repository reads named keys with ``.get()``, and the
ADR-041 export-skip gate reads only ``source_digest``, which is untouched.

Usage:
    uv run python scripts/stamp_build_identity.py
    uv run python scripts/stamp_build_identity.py --store data/assembled/grid.zarr
    uv run python scripts/stamp_build_identity.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from datafactory_provenance.build_identity import resolve_build_identity

DEFAULT_STORE = Path("data/assembled/grid.zarr")
REPO_DIR = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--store",
        type=Path,
        default=DEFAULT_STORE,
        help=f"zarr store to stamp (default: {DEFAULT_STORE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would be written, change nothing",
    )
    args = parser.parse_args()

    zattrs_path = args.store / ".zattrs"
    if not zattrs_path.exists():
        print(f"ERROR: no .zattrs at {zattrs_path}", file=sys.stderr)
        return 1

    try:
        attrs = json.loads(zattrs_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: cannot read {zattrs_path}: {exc}", file=sys.stderr)
        return 1

    identity = resolve_build_identity(REPO_DIR, "stamped")

    if identity["build_tag"] is None:
        print(
            "WARNING: this checkout is not on an exact tag, so the stamp "
            "will not name a release.\n"
            f"         {identity['build_identity_detail']}",
            file=sys.stderr,
        )

    print(f"Store:  {args.store}")
    print(f"Existing keys: {len(attrs)}")
    for key, value in identity.items():
        was = attrs.get(key, "—")
        print(f"  {key:<30} {was} -> {value}")

    if args.dry_run:
        print("\nDry run; nothing written.")
        return 0

    attrs.update(identity)
    # Write through a temporary file in the same directory, then replace,
    # so a store being served never sees a half-written .zattrs.
    tmp_path = zattrs_path.with_suffix(".zattrs.tmp")
    tmp_path.write_text(json.dumps(attrs, indent=4) + "\n")
    tmp_path.replace(zattrs_path)

    print(f"\nWrote {len(attrs)} keys to {zattrs_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
