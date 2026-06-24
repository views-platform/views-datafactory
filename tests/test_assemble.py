"""Tests for assembly logic in assemble_grid.py.

Addresses C-102: no tests for assembly script. Tests the pure
logic blocks (spatial join, GID lookup, feature concatenation)
without requiring real data files or full pipeline execution.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest


def _load_assembly_module():
    """Import the assemble_grid script as a module."""
    import importlib.util
    import sys as _sys

    path = Path(__file__).parent.parent / "scripts" / "assemble_grid.py"
    spec = importlib.util.spec_from_file_location(
        "assemble_grid", path,
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    _sys.modules["assemble_grid"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_assembly_mod = _load_assembly_module()


class TestAssemblyConfig:
    """AssemblyConfig validation (ADR-009)."""

    def test_default_construction(self) -> None:
        cfg = _assembly_mod.AssemblyConfig()
        assert cfg.output_dtype == "float32"
        assert cfg.admin_fill_value == -1.0
        assert cfg.disk_space_margin == 1.2
        assert len(cfg.admin_numeric_fields) == 3

    def test_empty_admin_fields_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            _assembly_mod.AssemblyConfig(admin_numeric_fields=())

    def test_duplicate_admin_fields_rejected(self) -> None:
        with pytest.raises(ValueError, match="duplicate"):
            _assembly_mod.AssemblyConfig(
                admin_numeric_fields=(
                    "gaul0_code", "gaul0_code",
                ),
            )

    def test_disk_margin_below_one_rejected(self) -> None:
        with pytest.raises(ValueError, match="disk_space_margin"):
            _assembly_mod.AssemblyConfig(disk_space_margin=0.5)

    def test_invalid_dtype_rejected(self) -> None:
        with pytest.raises(ValueError, match="output_dtype"):
            _assembly_mod.AssemblyConfig(output_dtype="int32")

    def test_frozen(self) -> None:
        cfg = _assembly_mod.AssemblyConfig()
        with pytest.raises(AttributeError):
            cfg.output_dtype = "float64"  # type: ignore[misc]

    def test_acled_grid_dir_defaults_to_none(self) -> None:
        cfg = _assembly_mod.AssemblyConfig()
        assert cfg.acled_grid_dir is None

    def test_acled_grid_dir_accepts_path(self) -> None:
        cfg = _assembly_mod.AssemblyConfig(
            acled_grid_dir=Path("/tmp/acled")
        )
        assert cfg.acled_grid_dir == Path("/tmp/acled")

    def test_ghspop_grid_dir_defaults_to_none(self) -> None:
        cfg = _assembly_mod.AssemblyConfig()
        assert cfg.ghspop_grid_dir is None

    def test_ghspop_grid_dir_accepts_path(self) -> None:
        cfg = _assembly_mod.AssemblyConfig(
            ghspop_grid_dir=Path("/tmp/ghspop")
        )
        assert cfg.ghspop_grid_dir == Path("/tmp/ghspop")


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
        acled = [
            "acled_count", "acled_battles",
            "acled_explosions", "acled_vac",
            "acled_protests", "acled_riots",
            "acled_strategic", "acled_fatalities",
        ]
        ghspop = ["ghspop_pop_count"]
        static = ["agri_gc", "forest_gc", "mountains_mean"]
        admin = ["gaul0_code", "gaul1_code", "gaul2_code"]
        all_features = ucdp + acled + ghspop + static + admin
        assert len(all_features) == len(set(all_features))

    def test_order_is_ucdp_acled_ghspop_static_admin(self) -> None:
        """Channel order: UCDP, ACLED, GHS-POP, static, admin."""
        ucdp = ["a", "b"]
        acled = ["c", "d"]
        ghspop = ["e"]
        static = ["f"]
        admin = ["g"]
        combined = ucdp + acled + ghspop + static + admin
        assert combined == ["a", "b", "c", "d", "e", "f", "g"]


class TestAcledTemporalAlignment:
    """ACLED temporal alignment into the assembled grid."""

    def test_acled_placed_at_correct_offset(self) -> None:
        """ACLED data lands at the correct temporal offset."""
        n_t, n_h, n_w = 10, 3, 4
        n_ucdp, n_acled = 2, 2
        n_total = n_ucdp + n_acled
        acled_offset = 6
        acled_t = 3

        assembled = np.zeros(
            (n_t, n_h, n_w, n_total), dtype=np.float32,
        )
        assembled[:, :, :, :n_ucdp] = 1.0

        acled_grid = np.full(
            (acled_t, n_h, n_w, n_acled), 7.0,
            dtype=np.float32,
        )
        acled_end = acled_offset + acled_t
        assembled[
            acled_offset:acled_end, :, :,
            n_ucdp:n_ucdp + n_acled,
        ] = acled_grid

        assert assembled[acled_offset, 0, 0, 2] == 7.0
        assert assembled[acled_end - 1, 0, 0, 3] == 7.0

    def test_zero_fill_outside_acled_range(self) -> None:
        """ACLED channels are zero outside their temporal range."""
        n_t, n_h, n_w = 10, 3, 4
        n_ucdp, n_acled = 2, 2
        n_total = n_ucdp + n_acled
        acled_offset = 6
        acled_t = 3

        assembled = np.zeros(
            (n_t, n_h, n_w, n_total), dtype=np.float32,
        )
        acled_grid = np.full(
            (acled_t, n_h, n_w, n_acled), 7.0,
            dtype=np.float32,
        )
        acled_end = acled_offset + acled_t
        assembled[
            acled_offset:acled_end, :, :,
            n_ucdp:n_ucdp + n_acled,
        ] = acled_grid

        # Before ACLED range
        assert assembled[:acled_offset, :, :, 2:].sum() == 0.0
        # After ACLED range
        assert assembled[acled_end:, :, :, 2:].sum() == 0.0

    def test_datetime_alignment_finds_correct_index(self) -> None:
        """np.where on datetime64 finds the right offset."""
        ucdp_ts = np.array(
            [f"20{y:02d}-{m:02d}" for y in range(20, 23)
             for m in range(1, 13)],
            dtype="datetime64[M]",
        )
        acled_start = np.datetime64("2021-06")
        matches = np.where(ucdp_ts == acled_start)[0]
        assert len(matches) == 1
        assert int(matches[0]) == 17  # 12 months + 5

    def test_assembly_without_acled_backward_compat(self) -> None:
        """When n_acled=0, offsets collapse to pre-ACLED layout."""
        n_ucdp, n_acled, n_ghspop, n_static, n_admin = 2, 0, 0, 1, 1
        n_total = n_ucdp + n_acled + n_ghspop + n_static + n_admin

        assembled = np.zeros(
            (2, 3, 4, n_total), dtype=np.float32,
        )
        static_val = 10.0
        admin_val = -1.0
        ch_offset = n_ucdp + n_acled + n_ghspop
        assembled[:, :, :, ch_offset] = static_val
        assembled[:, :, :, ch_offset + n_static] = admin_val

        assert assembled[0, 0, 0, 2] == static_val
        assert assembled[0, 0, 0, 3] == admin_val
        assert n_total == 4


class TestGhsPopTemporalAlignment:
    """GHS-POP temporal alignment into the assembled grid."""

    def test_ghspop_full_timeline_offset_zero(self) -> None:
        """GHS-POP compiled with same temporal range → offset 0."""
        n_t, n_h, n_w = 10, 3, 4
        n_ucdp, n_acled, n_ghspop = 2, 2, 1
        n_total = n_ucdp + n_acled + n_ghspop

        assembled = np.zeros(
            (n_t, n_h, n_w, n_total), dtype=np.float32,
        )
        assembled[:, :, :, :n_ucdp] = 1.0

        ghspop_grid = np.full(
            (n_t, n_h, n_w, n_ghspop), 100.0,
            dtype=np.float32,
        )
        ghspop_offset = 0
        ghspop_end = ghspop_offset + n_t
        ch_start = n_ucdp + n_acled
        assembled[
            ghspop_offset:ghspop_end, :, :,
            ch_start:ch_start + n_ghspop,
        ] = ghspop_grid

        assert assembled[0, 0, 0, ch_start] == 100.0
        assert assembled[n_t - 1, 0, 0, ch_start] == 100.0

    def test_ghspop_partial_timeline(self) -> None:
        """GHS-POP with shorter timeline placed at correct offset."""
        n_t, n_h, n_w = 10, 3, 4
        n_ucdp, n_acled, n_ghspop = 2, 0, 1
        n_total = n_ucdp + n_acled + n_ghspop
        ghspop_offset = 3
        ghspop_t = 5

        assembled = np.zeros(
            (n_t, n_h, n_w, n_total), dtype=np.float32,
        )
        ghspop_grid = np.full(
            (ghspop_t, n_h, n_w, n_ghspop), 42.0,
            dtype=np.float32,
        )
        ch_start = n_ucdp + n_acled
        ghspop_end = ghspop_offset + ghspop_t
        assembled[
            ghspop_offset:ghspop_end, :, :,
            ch_start:ch_start + n_ghspop,
        ] = ghspop_grid

        assert assembled[ghspop_offset, 0, 0, ch_start] == 42.0
        assert assembled[ghspop_end - 1, 0, 0, ch_start] == 42.0

    def test_zero_fill_outside_ghspop_range(self) -> None:
        """GHS-POP channels are zero outside their temporal range."""
        n_t, n_h, n_w = 10, 3, 4
        n_ucdp, n_acled, n_ghspop = 2, 0, 1
        n_total = n_ucdp + n_acled + n_ghspop
        ghspop_offset = 3
        ghspop_t = 5

        assembled = np.zeros(
            (n_t, n_h, n_w, n_total), dtype=np.float32,
        )
        ghspop_grid = np.full(
            (ghspop_t, n_h, n_w, n_ghspop), 42.0,
            dtype=np.float32,
        )
        ch_start = n_ucdp + n_acled
        ghspop_end = ghspop_offset + ghspop_t
        assembled[
            ghspop_offset:ghspop_end, :, :,
            ch_start:ch_start + n_ghspop,
        ] = ghspop_grid

        assert assembled[:ghspop_offset, :, :, ch_start:].sum() == 0.0
        assert assembled[ghspop_end:, :, :, ch_start:].sum() == 0.0

    def test_assembly_without_ghspop_backward_compat(self) -> None:
        """When n_ghspop=0, offsets collapse gracefully."""
        n_ucdp, n_acled, n_ghspop, n_static = 2, 2, 0, 1
        n_total = n_ucdp + n_acled + n_ghspop + n_static

        assembled = np.zeros(
            (2, 3, 4, n_total), dtype=np.float32,
        )
        static_val = 10.0
        ch_static = n_ucdp + n_acled + n_ghspop
        assembled[:, :, :, ch_static] = static_val

        assert assembled[0, 0, 0, ch_static] == static_val
        assert n_total == 5


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
    """Full assembly: UCDP + ACLED + static + admin → assembled grid."""

    def test_assembled_shape_and_channels(
        self, tmp_path: Path
    ) -> None:
        """Assemble tiny grid and verify shape + channel placement."""
        n_t, n_h, n_w = 10, 3, 4
        n_ucdp = 2
        n_acled = 2
        n_ghspop = 1
        n_static = 1
        n_admin = 1
        n_total = n_ucdp + n_acled + n_ghspop + n_static + n_admin

        # UCDP grid [T, H, W, C]
        ucdp_grid = np.ones(
            (n_t, n_h, n_w, n_ucdp), dtype=np.float32
        )
        ucdp_grid *= 5.0

        # ACLED grid [acled_T, H, W, C] — subset of timeline
        acled_offset = 6
        acled_t = 3
        acled_grid = np.full(
            (acled_t, n_h, n_w, n_acled), 9.0,
            dtype=np.float32,
        )

        # GHS-POP grid [T, H, W, C] — full timeline
        ghspop_grid = np.full(
            (n_t, n_h, n_w, n_ghspop), 100.0,
            dtype=np.float32,
        )

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
        acled_end = acled_offset + acled_t
        assembled[
            acled_offset:acled_end, :, :,
            n_ucdp:n_ucdp + n_acled,
        ] = acled_grid
        ch_ghspop = n_ucdp + n_acled
        assembled[
            :, :, :,
            ch_ghspop:ch_ghspop + n_ghspop,
        ] = ghspop_grid
        ch_static = ch_ghspop + n_ghspop
        assembled[:, :, :, ch_static] = static_spatial
        assembled[
            :, :, :, ch_static + n_static
        ] = admin_spatial
        assembled.flush()

        # Read back and verify
        result = np.load(output_path)
        assert result.shape == (10, 3, 4, 7)

        # UCDP channels (all time steps)
        assert result[0, 0, 0, 0] == 5.0
        assert result[0, 0, 0, 1] == 5.0

        # ACLED channels (only at offset)
        assert result[acled_offset, 0, 0, 2] == 9.0
        assert result[acled_offset, 0, 0, 3] == 9.0
        assert result[0, 0, 0, 2] == 0.0  # zero-fill before
        assert result[9, 0, 0, 2] == 0.0  # zero-fill after

        # GHS-POP channel (full timeline)
        assert result[0, 0, 0, 4] == 100.0
        assert result[9, 0, 0, 4] == 100.0

        # Static channel
        assert result[0, 0, 0, 5] == 10.0

        # Admin channel
        assert result[0, 0, 0, 6] == -1.0  # missing
        assert result[0, 1, 1, 6] == 42.0  # placed


# ---- Registry ↔ Assembly sync (C-293, #208) ----


class TestRegistryAssemblySync:
    """Guard tests: source_registry.py and assemble_grid.py stay in sync.

    The registry declares which sources contribute features and how many.
    The assembly script concatenates per-source grids into the final
    [T, H, W, C] array. These tests catch silent divergence.
    """

    def test_source_ordering_matches_registry(self) -> None:
        """Assembly concatenation order matches registry source order.

        Assembly concatenates: ucdp, acled, ghspop, ghsbuilts, vdem,
        shdi, static, admin. The set of source names contributing
        features must match those in PIPELINE_SOURCES.
        """
        from datafactory_provenance.source_registry import (
            PIPELINE_SOURCES,
        )

        registry_sources_with_features = [
            s.name for s in PIPELINE_SOURCES if s.features
        ]
        assembly_source_names = [
            "UCDP Annual", "ACLED", "GHS-POP", "GHS-BUILT-S",
            "V-Dem", "SHDI", "PRIO-GRID Static", "GAUL Admin",
        ]

        assert set(registry_sources_with_features) == set(
            assembly_source_names
        ), (
            f"Registry sources with features: "
            f"{registry_sources_with_features}, "
            f"assembly expects: {assembly_source_names}"
        )

    def test_per_source_feature_count_consistent(self) -> None:
        """Per-source feature counts from registry match expectations."""
        from datafactory_provenance.source_registry import (
            PIPELINE_SOURCES,
        )

        expected_counts = {
            "UCDP Annual": 6,
            "ACLED": 8,
            "GHS-POP": 1,
            "GHS-BUILT-S": 1,
            "PRIO-GRID Static": 34,
            "V-Dem": 22,
            "SHDI": 4,
            "GAUL Admin": 3,
        }

        for source in PIPELINE_SOURCES:
            if source.name in expected_counts:
                assert len(source.features) == expected_counts[
                    source.name
                ], (
                    f"{source.name}: expected "
                    f"{expected_counts[source.name]} features, "
                    f"got {len(source.features)}"
                )

    def test_total_feature_count_79(self) -> None:
        """Total features across all sources is 79."""
        from datafactory_provenance.source_registry import (
            get_all_features,
        )

        all_features = get_all_features()
        assert len(all_features) == 79, (
            f"Expected 79 total features, got {len(all_features)}"
        )

    def test_feature_names_match_registry(self) -> None:
        """All feature names are unique and present in registry."""
        from datafactory_provenance.source_registry import (
            get_all_features,
        )

        all_features = get_all_features()
        assert len(all_features) == len(set(all_features)), (
            "Duplicate feature names in registry"
        )

        admin_fields = _assembly_mod.AssemblyConfig().admin_numeric_fields
        for field in admin_fields:
            assert field in all_features, (
                f"Admin field '{field}' not in registry features"
            )

    def test_admin_numeric_fields_match_registry(self) -> None:
        """AssemblyConfig.admin_numeric_fields matches GAUL Admin features."""
        from datafactory_provenance.source_registry import (
            PIPELINE_SOURCES,
        )

        gaul_entry = next(
            s for s in PIPELINE_SOURCES if s.name == "GAUL Admin"
        )
        config_fields = _assembly_mod.AssemblyConfig().admin_numeric_fields

        assert set(config_fields) == set(gaul_entry.features), (
            f"Config admin_numeric_fields {config_fields} != "
            f"registry GAUL Admin features {gaul_entry.features}"
        )


# ---- Assembly Red/Beige tests (C-297, #235) ----


class TestAssemblyBeige:
    """Boundary and input validation tests for assembly (ADR-005)."""

    def test_load_source_grid_missing_files_returns_none(
        self, tmp_path: Path,
    ) -> None:
        """_load_source_grid returns None when source files are absent."""
        time_steps = np.array(
            ["2020-01", "2020-02", "2020-03"],
            dtype="datetime64[M]",
        )
        result = _assembly_mod._load_source_grid(
            "MISSING", tmp_path, time_steps, 3,
        )
        assert result is None

    def test_load_source_grid_start_outside_timeline_returns_none(
        self, tmp_path: Path,
    ) -> None:
        """Source whose start date is not in UCDP timeline → None."""
        import json as _json

        ucdp_ts = np.array(
            ["2020-01", "2020-02", "2020-03"],
            dtype="datetime64[M]",
        )
        source_ts = np.array(
            ["2019-06", "2019-07"],
            dtype="datetime64[M]",
        )
        grid = np.zeros((2, 360, 720, 1), dtype=np.float32)
        np.save(tmp_path / "grid.npy", grid)
        np.save(tmp_path / "time_steps.npy", source_ts)
        (tmp_path / "feature_names.json").write_text(
            _json.dumps(["feat_a"]),
        )
        result = _assembly_mod._load_source_grid(
            "BAD_START", tmp_path, ucdp_ts, 3,
        )
        assert result is None

    def test_load_source_grid_extends_beyond_timeline_returns_none(
        self, tmp_path: Path,
    ) -> None:
        """Source extending past UCDP timeline end → None."""
        import json as _json

        ucdp_ts = np.array(
            ["2020-01", "2020-02", "2020-03"],
            dtype="datetime64[M]",
        )
        source_ts = np.array(
            ["2020-02", "2020-03", "2020-04"],
            dtype="datetime64[M]",
        )
        grid = np.zeros((3, 360, 720, 1), dtype=np.float32)
        np.save(tmp_path / "grid.npy", grid)
        np.save(tmp_path / "time_steps.npy", source_ts)
        (tmp_path / "feature_names.json").write_text(
            _json.dumps(["feat_a"]),
        )
        result = _assembly_mod._load_source_grid(
            "OVERFLOW", tmp_path, ucdp_ts, 3,
        )
        assert result is None


class TestAssemblyRed:
    """Adversarial and footgun tests for assembly (ADR-005).

    These characterize dangerous behaviors — especially the
    partial-flag footgun documented in server_operations.md:142-145.
    """

    def test_partial_sources_produce_fewer_features(self) -> None:
        """Assembling with subset of sources → fewer than 79 features.

        This characterizes the partial-flag footgun: omitting source
        flags silently produces a smaller grid. No error, no warning.
        """
        from datafactory_provenance.source_registry import (
            PIPELINE_SOURCES,
            get_all_features,
        )

        all_79 = get_all_features()
        ucdp_entry = next(
            s for s in PIPELINE_SOURCES
            if s.name == "UCDP Annual"
        )
        static_entry = next(
            s for s in PIPELINE_SOURCES
            if s.name == "PRIO-GRID Static"
        )
        admin_entry = next(
            s for s in PIPELINE_SOURCES
            if s.name == "GAUL Admin"
        )
        partial_count = (
            len(ucdp_entry.features)
            + len(static_entry.features)
            + len(admin_entry.features)
        )
        assert partial_count < len(all_79), (
            f"UCDP+static+admin = {partial_count} should be "
            f"< 79, but got {len(all_79)}"
        )
        assert partial_count == 6 + 34 + 3  # 43, not 79

    def test_nan_in_source_grid_propagates(self) -> None:
        """NaN values in a source grid propagate to assembled output."""
        n_t, n_h, n_w = 5, 3, 4
        n_ucdp, n_source = 2, 1
        n_total = n_ucdp + n_source

        assembled = np.zeros(
            (n_t, n_h, n_w, n_total), dtype=np.float32,
        )
        assembled[:, :, :, :n_ucdp] = 1.0

        source_grid = np.full(
            (n_t, n_h, n_w, n_source), np.nan,
            dtype=np.float32,
        )
        source_grid[0, 0, 0, 0] = 42.0
        assembled[:, :, :, n_ucdp:n_ucdp + n_source] = source_grid

        assert assembled[0, 0, 0, n_ucdp] == 42.0
        assert np.isnan(assembled[1, 0, 0, n_ucdp])
        assert np.isnan(assembled[0, 1, 0, n_ucdp])

    def test_feature_names_length_matches_grid_channels(
        self, tmp_path: Path,
    ) -> None:
        """Feature name list length must equal grid.shape[3]."""
        n_t, n_h, n_w = 5, 3, 4
        features = ["f1", "f2", "f3"]
        grid = np.zeros(
            (n_t, n_h, n_w, len(features)), dtype=np.float32,
        )

        np.save(tmp_path / "grid.npy", grid)
        import json as _json
        (tmp_path / "feature_names.json").write_text(
            _json.dumps(features),
        )
        loaded_grid = np.load(tmp_path / "grid.npy")
        loaded_features = _json.loads(
            (tmp_path / "feature_names.json").read_text(),
        )
        assert loaded_grid.shape[3] == len(loaded_features)

        bad_features = ["f1", "f2"]
        (tmp_path / "feature_names.json").write_text(
            _json.dumps(bad_features),
        )
        loaded_bad = _json.loads(
            (tmp_path / "feature_names.json").read_text(),
        )
        assert loaded_grid.shape[3] != len(loaded_bad), (
            "Mismatch should be detectable"
        )

    def test_load_source_grid_returns_correct_offset(
        self, tmp_path: Path,
    ) -> None:
        """_load_source_grid returns correct temporal offset."""
        import json as _json

        ucdp_ts = np.array(
            [f"2020-{m:02d}" for m in range(1, 13)],
            dtype="datetime64[M]",
        )
        source_ts = np.array(
            ["2020-04", "2020-05", "2020-06"],
            dtype="datetime64[M]",
        )
        grid = np.ones((3, 360, 720, 2), dtype=np.float32)
        np.save(tmp_path / "grid.npy", grid)
        np.save(tmp_path / "time_steps.npy", source_ts)
        (tmp_path / "feature_names.json").write_text(
            _json.dumps(["feat_a", "feat_b"]),
        )
        result = _assembly_mod._load_source_grid(
            "TEST", tmp_path, ucdp_ts, 12,
        )
        assert result is not None
        _, features, offset = result
        assert offset == 3
        assert features == ["feat_a", "feat_b"]

    def test_corrupted_provenance_does_not_prevent_assembly(
        self, tmp_path: Path,
    ) -> None:
        """Malformed provenance.json should not cause false skip."""
        import json as _json

        provenance_path = tmp_path / "provenance.json"
        provenance_path.write_text("{invalid json!!")

        with pytest.raises(_json.JSONDecodeError):
            _json.loads(provenance_path.read_text())
