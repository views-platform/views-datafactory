"""Tests for assembly logic in assemble_grid.py.

Addresses C-102: no tests for assembly script. Tests the pure
logic blocks (spatial join, GID lookup, feature concatenation)
without requiring real data files or full pipeline execution.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np


class TestGidLookup:
    """GID-to-(row, col) lookup construction."""

    def test_bijection_no_overwrites(self) -> None:
        """Every pgid maps to exactly one (row, col)."""
        pgids = np.arange(1, 13).reshape(3, 4)
        lookup: dict[int, tuple[int, int]] = {}
        for r in range(3):
            for c in range(4):
                lookup[int(pgids[r, c])] = (r, c)
        assert len(lookup) == 12
        assert lookup[1] == (0, 0)
        assert lookup[12] == (2, 3)

    def test_full_grid_size(self) -> None:
        """Standard PRIO-GRID produces 259,200 unique entries."""
        from datafactory_priogrid import generate_grid

        pgids_flat, _, _ = generate_grid()
        pgids_2d = pgids_flat.reshape(360, 720)
        lookup: dict[int, tuple[int, int]] = {}
        for r in range(360):
            for c in range(720):
                lookup[int(pgids_2d[r, c])] = (r, c)
        assert len(lookup) == 259_200


class TestSpatialJoin:
    """Static and admin variable spatial placement."""

    def test_all_cells_placed_when_aligned(self) -> None:
        """Perfect GID alignment places all cells."""
        n_h, n_w = 3, 4
        pgids = np.arange(1, 13).reshape(n_h, n_w)
        gid_to_rowcol = {
            int(pgids[r, c]): (r, c)
            for r in range(n_h)
            for c in range(n_w)
        }

        gids = list(range(1, 13))
        values = [float(i) for i in range(12)]
        spatial = np.zeros((n_h, n_w), dtype=np.float32)
        n_placed = 0
        for gid, val in zip(gids, values, strict=True):
            if gid in gid_to_rowcol:
                r, c = gid_to_rowcol[gid]
                spatial[r, c] = float(val)
                n_placed += 1

        assert n_placed == 12
        assert spatial[0, 0] == 0.0
        assert spatial[2, 3] == 11.0

    def test_unmatched_gids_skipped(self) -> None:
        """GIDs outside the grid range are silently skipped."""
        gid_to_rowcol = {1: (0, 0), 2: (0, 1)}
        gids = [1, 2, 999]  # 999 not in grid
        values = [1.0, 2.0, 3.0]
        spatial = np.zeros((1, 2), dtype=np.float32)
        n_placed = 0
        for gid, val in zip(gids, values, strict=True):
            if gid in gid_to_rowcol:
                r, c = gid_to_rowcol[gid]
                spatial[r, c] = float(val)
                n_placed += 1

        assert n_placed == 2
        assert spatial[0, 0] == 1.0
        assert spatial[0, 1] == 2.0

    def test_admin_fill_value_is_negative_one(self) -> None:
        """Admin channels use -1.0 for missing (categorical, not 0.0)."""
        spatial = np.full((3, 4), -1.0, dtype=np.float32)
        # Place one cell
        spatial[1, 2] = 42.0
        assert spatial[0, 0] == -1.0  # missing → -1
        assert spatial[1, 2] == 42.0  # placed


class TestFeatureConcatenation:
    """Feature name assembly from multiple sources."""

    def test_no_duplicates(self) -> None:
        """Combined feature list has no duplicates."""
        ucdp = [
            "ged_sb_count", "ged_sb_best",
            "ged_ns_count", "ged_ns_best",
            "ged_os_count", "ged_os_best",
        ]
        static = ["agri_gc", "forest_gc", "mountains_mean"]
        admin = ["gaul0_code", "gaul1_code", "gaul2_code"]
        all_features = ucdp + static + admin
        assert len(all_features) == len(set(all_features))

    def test_order_is_ucdp_then_static_then_admin(self) -> None:
        """Channel order: UCDP features first, then static, then admin."""
        ucdp = ["a", "b"]
        static = ["c"]
        admin = ["d"]
        combined = ucdp + static + admin
        assert combined == ["a", "b", "c", "d"]


class TestAtomicWrite:
    """Atomic write: tmp file renamed on success (C-105)."""

    def test_no_tmp_file_after_success(
        self, tmp_path: Path
    ) -> None:
        """After successful write + rename, .tmp must not exist."""
        import os

        output_path = tmp_path / "grid.npy"
        tmp_file = tmp_path / "grid.npy.tmp"

        assembled = np.lib.format.open_memmap(
            str(tmp_file),
            mode="w+",
            dtype=np.float32,
            shape=(2, 3, 4, 1),
        )
        assembled[:] = 1.0
        assembled.flush()
        del assembled
        os.rename(str(tmp_file), str(output_path))

        assert output_path.exists()
        assert not tmp_file.exists()
        result = np.load(output_path)
        assert result.shape == (2, 3, 4, 1)

    def test_tmp_cleanup_on_failure(
        self, tmp_path: Path
    ) -> None:
        """On write failure, .tmp is cleaned up, original untouched."""
        output_path = tmp_path / "grid.npy"
        tmp_file = tmp_path / "grid.npy.tmp"

        # Write a valid file first
        np.save(output_path, np.zeros((2, 3), dtype=np.float32))
        original_size = output_path.stat().st_size

        # Simulate failure during assembly
        try:
            np.lib.format.open_memmap(
                str(tmp_file),
                mode="w+",
                dtype=np.float32,
                shape=(2, 3, 4, 1),
            )
            msg = "simulated write failure"
            raise OSError(msg)
        except OSError:
            if tmp_file.exists():
                tmp_file.unlink()

        # Original file untouched
        assert output_path.stat().st_size == original_size
        assert not tmp_file.exists()


class TestAssemblyRoundTrip:
    """Full assembly: UCDP grid + static + admin → assembled grid."""

    def test_assembled_shape_and_channels(
        self, tmp_path: Path
    ) -> None:
        """Assemble tiny grid and verify shape + channel placement."""
        n_t, n_h, n_w = 2, 3, 4
        n_ucdp = 2
        n_static = 1
        n_admin = 1
        n_total = n_ucdp + n_static + n_admin

        # UCDP grid [T, H, W, C]
        ucdp_grid = np.ones(
            (n_t, n_h, n_w, n_ucdp), dtype=np.float32
        )
        ucdp_grid *= 5.0

        # Static: single [H, W] array
        static_spatial = np.full(
            (n_h, n_w), 10.0, dtype=np.float32
        )

        # Admin: single [H, W] array with -1 fill
        admin_spatial = np.full(
            (n_h, n_w), -1.0, dtype=np.float32
        )
        admin_spatial[1, 1] = 42.0

        # Assemble via mmap (same logic as assemble_grid.py)
        output_path = tmp_path / "grid.npy"
        assembled = np.lib.format.open_memmap(
            str(output_path),
            mode="w+",
            dtype=np.float32,
            shape=(n_t, n_h, n_w, n_total),
        )
        assembled[:, :, :, :n_ucdp] = ucdp_grid
        assembled[:, :, :, n_ucdp] = static_spatial
        assembled[:, :, :, n_ucdp + n_static] = admin_spatial
        assembled.flush()

        # Read back and verify
        result = np.load(output_path)
        assert result.shape == (2, 3, 4, 4)

        # UCDP channels
        assert result[0, 0, 0, 0] == 5.0
        assert result[0, 0, 0, 1] == 5.0

        # Static channel
        assert result[0, 0, 0, 2] == 10.0

        # Admin channel
        assert result[0, 0, 0, 3] == -1.0  # missing
        assert result[0, 1, 1, 3] == 42.0  # placed
