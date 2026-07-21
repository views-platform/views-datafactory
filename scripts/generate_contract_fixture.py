#!/usr/bin/env python3
"""Generate the FeatureFrame conformance fixture (ADR-050, #344).

The committed fixture at tests/fixtures/feature_frame_contract/frame/
is the executable specification of the FeatureFrame on-disk layout:
it is real output of ``views_frames.FeatureFrame.save()``, never
hand-authored (fixture policy, ADR-050 — the C-315 generalization).

Regeneration is a deliberate act:

    uv run python scripts/generate_contract_fixture.py

Re-running on the same views-frames version is byte-identical
(verified: save() pins zip timestamps). A diff after a views-frames
upgrade means the layout changed — review it, bump CONTRACT_VERSION
in contract.json, and coordinate with consumers per ADR-050.

Usage:
    uv run python scripts/generate_contract_fixture.py            # regenerate
    uv run python scripts/generate_contract_fixture.py --check    # verify only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

from datafactory_provenance import compute_file_digest

FIXTURE_DIR = Path("tests/fixtures/feature_frame_contract")
FRAME_DIR = FIXTURE_DIR / "frame"
CONTRACT_PATH = FIXTURE_DIR / "contract.json"

# Fixed, meaningful content: two months (2025-01, 2025-02 in VIEWS
# month_ids), three PRIO-GRID cells, two features, one sample axis.
# Values are small distinct integers so a corrupted byte is visible
# in a diff, not just in a digest.
_TIME = [541, 541, 541, 542, 542, 542]
_UNIT = [149426, 150146, 150866, 149426, 150146, 150866]
_FEATURES = ["ged_sb_best", "acled_fatalities"]
_VALUES = [
    [[1.0], [10.0]],
    [[2.0], [20.0]],
    [[3.0], [30.0]],
    [[4.0], [40.0]],
    [[5.0], [50.0]],
    [[6.0], [60.0]],
]


def build_contract_frame():  # noqa: ANN201 — views_frames type
    """Build the canonical fixture frame (deterministic)."""
    from views_frames import (
        FeatureFrame,
        SpatialLevel,
        SpatioTemporalIndex,
    )

    index = SpatioTemporalIndex(
        time=np.array(_TIME, dtype=np.int64),
        unit=np.array(_UNIT, dtype=np.int64),
        level=SpatialLevel.PGM,
    )
    return FeatureFrame(
        y_features=np.array(_VALUES, dtype=np.float32),
        index=index,
        feature_names=list(_FEATURES),
    )


def fixture_digest(frame_dir: Path) -> str:
    """Composite sha256 over the frame directory, order-stable."""
    parts = []
    for p in sorted(frame_dir.iterdir()):
        parts.append(f"{p.name}:{compute_file_digest(p)}")
    return hashlib.sha256(
        "\n".join(parts).encode()
    ).hexdigest()[:16]


def generate(dest: Path) -> str:
    """Save the canonical frame to dest; return its digest."""
    build_contract_frame().save(dest)
    return fixture_digest(dest)


def main() -> int:
    """Regenerate (or --check) the committed fixture."""
    parser = argparse.ArgumentParser(
        description="Generate the FeatureFrame conformance fixture"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify committed fixture matches contract.json; "
        "write nothing.",
    )
    args = parser.parse_args()

    if args.check:
        actual = fixture_digest(FRAME_DIR)
        recorded = json.loads(CONTRACT_PATH.read_text())[
            "fixture_digest"
        ]
        if actual != recorded:
            print(
                f"MISMATCH: fixture digest {actual} != "
                f"contract.json {recorded}"
            )
            return 1
        print(f"OK: fixture digest {actual} matches contract.json")
        return 0

    digest = generate(FRAME_DIR)
    contract = json.loads(CONTRACT_PATH.read_text())
    old = contract.get("fixture_digest")
    contract["fixture_digest"] = digest
    CONTRACT_PATH.write_text(
        json.dumps(contract, indent=2) + "\n"
    )
    print(f"Fixture written to {FRAME_DIR}")
    print(f"Digest: {old} -> {digest}")
    if old not in (None, digest):
        print(
            "Digest CHANGED — the layout or content moved. Per "
            "ADR-050: review the diff, bump contract_version, "
            "coordinate with consumers."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
