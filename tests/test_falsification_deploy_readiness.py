"""Falsification stubs — deploy readiness (2026-06-08).

These tests encode the hard and soft falsifications found during
the pre-merge-to-main audit. They are designed to fail until the
underlying issues are resolved.

Source: /falsify "if we merge to main now and deploy, there will
be no nasty surprises"
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

ASSEMBLED_DIR = Path("data/assembled")


@pytest.mark.skipif(
    not (ASSEMBLED_DIR / "grid.npy").exists()
    or not (ASSEMBLED_DIR / "grid.zarr").exists(),
    reason="Requires assembled grid and zarr",
)
class TestF1ZarrNpyStaleness:
    """P1/P6: Zarr must reflect the current npy grid."""

    def test_zarr_acled_2025_matches_npy(self) -> None:
        """Zarr 2025 ACLED count must match npy.

        Fails when zarr is stale and still contains the doubled
        ACLED events from pre-fix grid (822k vs 411k).
        """
        import zarr

        z = zarr.open(str(ASSEMBLED_DIR / "grid.zarr"), "r")
        acled_count = z["acled_count"]

        # 2025: indices 432-443 in assembled grid
        zarr_2025 = sum(
            float(np.nansum(acled_count[m]))
            for m in range(432, 444)
        )

        grid = np.load(
            ASSEMBLED_DIR / "grid.npy", mmap_mode="r",
        )
        features = json.loads(
            (ASSEMBLED_DIR / "feature_names.json").read_text()
        )
        acled_idx = features.index("acled_count")
        npy_2025 = float(grid[432:444, :, :, acled_idx].sum())

        assert int(zarr_2025) == int(npy_2025), (
            f"Zarr 2025 ACLED ({int(zarr_2025):,}) != "
            f"npy ({int(npy_2025):,}). "
            f"Ratio: {zarr_2025 / npy_2025:.2f}x. "
            f"Re-export zarr: uv run python scripts/export_zarr.py"
        )


@pytest.mark.skipif(
    not (ASSEMBLED_DIR / "grid.npy").exists()
    or not (ASSEMBLED_DIR / "grid.zarr").exists(),
    reason="Requires assembled grid and zarr",
)
class TestF2ZarrTimestamp:
    """P5: Zarr must not be older than the npy it was exported from."""

    def test_zarr_not_stale(self) -> None:
        """Zarr export timestamp must be >= npy mtime.

        Fails when the grid was reassembled but zarr was not
        re-exported, meaning the server would serve stale data.
        """
        import os

        npy_mtime = os.path.getmtime(ASSEMBLED_DIR / "grid.npy")
        zarr_mtime = os.path.getmtime(
            ASSEMBLED_DIR / "grid.zarr" / ".zattrs"
        )

        assert zarr_mtime >= npy_mtime, (
            "Zarr (.zattrs mtime) is older than grid.npy. "
            "Zarr was exported before the grid was reassembled. "
            "Re-export: uv run python scripts/export_zarr.py"
        )
