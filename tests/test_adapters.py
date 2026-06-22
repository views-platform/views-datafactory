"""Tests for datafactory_adapters — FeatureFrame + conversions."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from datafactory_adapters import (
    FeatureFrame,
    FrameMetadata,
    SpatialLevel,
    SpatioTemporalIndex,
    feature_frame_to_grid,
    grid_to_dataframe,
    grid_to_feature_frame,
)

# ---- FeatureFrame: Green ----


class TestFeatureFrameGreen:

    def test_construction(self) -> None:
        index = SpatioTemporalIndex(
            time=np.arange(10, dtype=np.int64),
            unit=np.arange(10, dtype=np.int64),
            level=SpatialLevel.PGM,
        )
        ff = FeatureFrame.from_2d(
            y_features_2d=np.zeros((10, 3)),
            index=index,
            feature_names=["a", "b", "c"],
        )
        assert ff.n_rows == 10
        assert ff.n_features == 3
        assert ff.sample_count == 1
        assert not ff.is_sample

    def test_3d_with_samples(self) -> None:
        index = SpatioTemporalIndex(
            time=np.arange(10, dtype=np.int64),
            unit=np.arange(10, dtype=np.int64),
            level=SpatialLevel.PGM,
        )
        ff = FeatureFrame(
            y_features=np.zeros((10, 3, 5), dtype=np.float32),
            index=index,
            feature_names=["a", "b", "c"],
        )
        assert ff.sample_count == 5
        assert ff.is_sample

    def test_save_load_roundtrip(
        self, tmp_path: Path
    ) -> None:
        index = SpatioTemporalIndex(
            time=np.arange(10, dtype=np.int64),
            unit=np.arange(100, 110, dtype=np.int64),
            level=SpatialLevel.PGM,
        )
        original = FeatureFrame.from_2d(
            y_features_2d=np.random.rand(10, 3).astype(
                np.float32
            ),
            index=index,
            feature_names=["x", "y", "z"],
            metadata=FrameMetadata(model="test"),
        )
        original.save(tmp_path / "ff")
        loaded = FeatureFrame.load(tmp_path / "ff")

        np.testing.assert_array_equal(
            original.values, loaded.values
        )
        assert loaded.feature_names == ["x", "y", "z"]
        assert loaded.metadata.model == "test"

    def test_dtype_coerced_to_float32(self) -> None:
        index = SpatioTemporalIndex(
            time=np.arange(5, dtype=np.int64),
            unit=np.arange(5, dtype=np.int64),
            level=SpatialLevel.PGM,
        )
        ff = FeatureFrame.from_2d(
            y_features_2d=np.zeros((5, 2), dtype=np.float64),
            index=index,
            feature_names=["a", "b"],
        )
        assert ff.values.dtype == np.float32


# ---- FeatureFrame: Beige ----


class TestFeatureFrameBeige:

    def test_missing_time_raises(self) -> None:
        with pytest.raises(TypeError):
            SpatioTemporalIndex(
                unit=np.arange(5, dtype=np.int64),
                level=SpatialLevel.PGM,
            )

    def test_missing_unit_raises(self) -> None:
        with pytest.raises(TypeError):
            SpatioTemporalIndex(
                time=np.arange(5, dtype=np.int64),
                level=SpatialLevel.PGM,
            )

    def test_wrong_feature_names_count(self) -> None:
        index = SpatioTemporalIndex(
            time=np.arange(5, dtype=np.int64),
            unit=np.arange(5, dtype=np.int64),
            level=SpatialLevel.PGM,
        )
        with pytest.raises(ValueError, match="feature_names"):
            FeatureFrame.from_2d(
                y_features_2d=np.zeros((5, 3)),
                index=index,
                feature_names=["a", "b"],  # 2 != 3
            )

    def test_identifier_length_mismatch(self) -> None:
        with pytest.raises(ValueError, match="length"):
            SpatioTemporalIndex(
                time=np.arange(3, dtype=np.int64),  # 3 != 5
                unit=np.arange(5, dtype=np.int64),
                level=SpatialLevel.PGM,
            )

    def test_1d_features_raises(self) -> None:
        index = SpatioTemporalIndex(
            time=np.arange(5, dtype=np.int64),
            unit=np.arange(5, dtype=np.int64),
            level=SpatialLevel.PGM,
        )
        with pytest.raises(ValueError, match="2D"):
            FeatureFrame.from_2d(
                y_features_2d=np.zeros(5),
                index=index,
                feature_names=["a"],
            )


# ---- grid_to_dataframe: Green ----


class TestGridToDataframeGreen:

    def test_basic_conversion(self) -> None:
        grid = np.ones((2, 3, 4, 2), dtype=np.float32)
        pgids = np.arange(1, 13).reshape(3, 4)
        time_steps = np.array(
            ["2024-01", "2024-02"],
            dtype="datetime64[M]",
        )
        features = ["count", "fatalities"]

        df = grid_to_dataframe(
            grid, pgids, time_steps, features
        )

        assert list(df.columns) == ["count", "fatalities"]
        assert df.index.names == [
            "month_id", "priogrid_gid"
        ]
        # 2 months × 12 cells = 24 rows
        assert len(df) == 24

    def test_land_filter(self) -> None:
        grid = np.ones((1, 2, 2, 1), dtype=np.float32)
        pgids = np.array([[1, 2], [3, 4]])
        time_steps = np.array(
            ["2024-01"], dtype="datetime64[M]"
        )

        df = grid_to_dataframe(
            grid, pgids, time_steps, ["x"],
            land_pgids={1, 3},
        )
        assert len(df) == 2  # Only cells 1 and 3

    def test_sparse_filter(self) -> None:
        grid = np.zeros((1, 2, 2, 1), dtype=np.float32)
        grid[0, 0, 0, 0] = 5.0  # One non-zero cell
        pgids = np.array([[1, 2], [3, 4]])
        time_steps = np.array(
            ["2024-01"], dtype="datetime64[M]"
        )

        df = grid_to_dataframe(
            grid, pgids, time_steps, ["x"],
            sparse=True,
        )
        assert len(df) == 1

    def test_month_id_epoch(self) -> None:
        grid = np.ones((1, 1, 1, 1), dtype=np.float32)
        pgids = np.array([[1]])
        time_steps = np.array(
            ["2024-01"], dtype="datetime64[M]"
        )

        df_raw = grid_to_dataframe(
            grid, pgids, time_steps, ["x"],
            month_id_epoch=0,
        )
        df_views = grid_to_dataframe(
            grid, pgids, time_steps, ["x"],
            month_id_epoch=1980,
        )

        raw_id = df_raw.index.get_level_values(
            "month_id"
        )[0]
        views_id = df_views.index.get_level_values(
            "month_id"
        )[0]
        # VIEWS month_id = raw - 1980*12
        assert views_id == raw_id - 1980 * 12


# ---- grid_to_feature_frame: Green ----


class TestGridToFeatureFrameGreen:

    def test_basic_conversion(self) -> None:
        grid = np.ones((2, 3, 4, 2), dtype=np.float32)
        pgids = np.arange(1, 13).reshape(3, 4)
        time_steps = np.array(
            ["2024-01", "2024-02"],
            dtype="datetime64[M]",
        )

        ff = grid_to_feature_frame(
            grid, pgids, time_steps,
            ["count", "best"],
        )

        assert ff.n_rows == 24  # 2 months × 12 cells
        assert ff.n_features == 2
        assert ff.feature_names == ["count", "best"]
        assert "time" in ff.identifiers
        assert "unit" in ff.identifiers

    def test_land_filter(self) -> None:
        grid = np.ones((1, 2, 2, 1), dtype=np.float32)
        pgids = np.array([[1, 2], [3, 4]])
        time_steps = np.array(
            ["2024-01"], dtype="datetime64[M]"
        )

        ff = grid_to_feature_frame(
            grid, pgids, time_steps, ["x"],
            land_pgids={1, 3},
        )
        assert ff.n_rows == 2


# ---- FeatureFrame: Red (C-55) ----


class TestFeatureFrameRed:

    def test_zero_rows_accepted(self) -> None:
        index = SpatioTemporalIndex(
            time=np.array([], dtype=np.int64),
            unit=np.array([], dtype=np.int64),
            level=SpatialLevel.PGM,
        )
        ff = FeatureFrame.from_2d(
            y_features_2d=np.zeros((0, 2), dtype=np.float32),
            index=index,
            feature_names=["a", "b"],
        )
        assert ff.n_rows == 0

    def test_save_to_nonexistent_parent(
        self, tmp_path: Path
    ) -> None:
        """Save should create directories."""
        index = SpatioTemporalIndex(
            time=np.arange(3, dtype=np.int64),
            unit=np.arange(3, dtype=np.int64),
            level=SpatialLevel.PGM,
        )
        ff = FeatureFrame.from_2d(
            y_features_2d=np.ones((3, 2), dtype=np.float32),
            index=index,
            feature_names=["a", "b"],
        )
        deep_path = tmp_path / "a" / "b" / "c"
        ff.save(deep_path)
        loaded = FeatureFrame.load(deep_path)
        assert loaded.n_rows == 3


# ---- month_id: Beige (C-57) ----


class TestMonthIdBeige:

    def test_epoch_boundary_jan_1980(self) -> None:
        """Jan 1980 with epoch=1980 should be month_id=1."""
        from datafactory_adapters.grid_to_dataframe import (
            _compute_month_ids,
        )

        ts = np.array(["1980-01"], dtype="datetime64[M]")
        result = _compute_month_ids(ts, epoch=1980)
        assert result[0] == 1

    def test_before_epoch(self) -> None:
        """Dec 1979 with epoch=1980 should be month_id=0."""
        from datafactory_adapters.grid_to_dataframe import (
            _compute_month_ids,
        )

        ts = np.array(["1979-12"], dtype="datetime64[M]")
        result = _compute_month_ids(ts, epoch=1980)
        assert result[0] == 0

    def test_full_range_1989_2026(self) -> None:
        """Verify month_ids for the full operational range."""
        from datafactory_adapters.grid_to_dataframe import (
            _compute_month_ids,
        )

        ts = np.array(
            ["1989-01", "2024-12", "2026-12"],
            dtype="datetime64[M]",
        )
        result = _compute_month_ids(ts, epoch=1980)
        assert result[0] == 109
        assert result[1] == 540
        assert result[2] == 564

    def test_raw_epoch_zero(self) -> None:
        """Raw epoch (0) gives large month_ids."""
        from datafactory_adapters.grid_to_dataframe import (
            _compute_month_ids,
        )

        ts = np.array(["2024-01"], dtype="datetime64[M]")
        raw = _compute_month_ids(ts, epoch=0)
        views = _compute_month_ids(ts, epoch=1980)
        assert raw[0] == views[0] + 1980 * 12


# ---- Adapter roundtrip: Green (C-58) ----


class TestAdapterRoundtripGreen:

    def test_grid_to_df_to_ff_roundtrip(self) -> None:
        """Full chain: grid → DataFrame → FeatureFrame."""
        grid = np.random.rand(
            2, 3, 4, 2
        ).astype(np.float32)
        pgids = np.arange(1, 13).reshape(3, 4)
        time_steps = np.array(
            ["2024-01", "2024-02"],
            dtype="datetime64[M]",
        )
        features = ["count", "best"]

        df = grid_to_dataframe(
            grid, pgids, time_steps, features,
        )
        ff = grid_to_feature_frame(
            grid, pgids, time_steps, features,
        )

        assert len(df) == ff.n_rows
        np.testing.assert_allclose(
            df.values.sum(), ff.values.sum(), rtol=1e-5
        )

    def test_ff_save_load_preserves_data(
        self, tmp_path: Path
    ) -> None:
        """FeatureFrame save → load roundtrip."""
        grid = np.random.rand(
            2, 3, 4, 2
        ).astype(np.float32)
        pgids = np.arange(1, 13).reshape(3, 4)
        time_steps = np.array(
            ["2024-01", "2024-02"],
            dtype="datetime64[M]",
        )

        ff = grid_to_feature_frame(
            grid, pgids, time_steps,
            ["count", "best"],
        )
        ff.save(tmp_path / "roundtrip")
        loaded = FeatureFrame.load(tmp_path / "roundtrip")

        assert loaded.n_rows == ff.n_rows
        assert loaded.feature_names == ff.feature_names
        np.testing.assert_array_equal(
            loaded.values, ff.values
        )


# ---- grid_to_feature_frame via function: Green (C-64) ----


class TestFeatureFrameFromGridGreen:

    def test_from_grid_function(self) -> None:
        grid = np.ones((2, 3, 4, 2), dtype=np.float32)
        pgids = np.arange(1, 13).reshape(3, 4)
        time_steps = np.array(
            ["2024-01", "2024-02"],
            dtype="datetime64[M]",
        )

        ff = grid_to_feature_frame(
            grid, pgids, time_steps, ["a", "b"]
        )
        assert ff.n_rows == 24
        assert ff.n_features == 2


# ---- Identifier alignment: Green (C-65) ----


class TestIdentifierAlignmentGreen:

    def test_required_identifiers_match_prediction_frame(
        self,
    ) -> None:
        """FeatureFrame uses same required identifiers
        as PredictionFrame: 'time' and 'unit'.
        """
        from datafactory_adapters.feature_frame import (
            REQUIRED_IDENTIFIERS,
        )

        # PredictionFrame requires {"time", "unit"}
        assert "time" in REQUIRED_IDENTIFIERS
        assert "unit" in REQUIRED_IDENTIFIERS

    def test_feature_frame_identifiers_present(
        self,
    ) -> None:
        index = SpatioTemporalIndex(
            time=np.arange(5, dtype=np.int64),
            unit=np.arange(5, dtype=np.int64),
            level=SpatialLevel.PGM,
        )
        ff = FeatureFrame.from_2d(
            y_features_2d=np.ones((5, 2)),
            index=index,
            feature_names=["a", "b"],
        )
        assert "time" in ff.identifiers
        assert "unit" in ff.identifiers


# ---- Grid roundtrip parity: Green (C-70) ----


class TestGridRoundtripParityGreen:

    def test_grid_to_ff_to_grid_exact(self) -> None:
        """Grid → FeatureFrame → grid is lossless."""
        grid = np.random.rand(
            2, 3, 4, 2
        ).astype(np.float32)
        pgids = np.arange(1, 13).reshape(3, 4)
        time_steps = np.array(
            ["2024-01", "2024-02"],
            dtype="datetime64[M]",
        )

        ff = grid_to_feature_frame(
            grid, pgids, time_steps, ["a", "b"],
        )
        reconstructed = feature_frame_to_grid(ff, pgids)

        np.testing.assert_array_equal(grid, reconstructed)

    def test_roundtrip_with_save_load(
        self, tmp_path: Path
    ) -> None:
        """Grid → FF → save → load → grid is lossless."""
        grid = np.random.rand(
            2, 3, 4, 2
        ).astype(np.float32)
        pgids = np.arange(1, 13).reshape(3, 4)
        time_steps = np.array(
            ["2024-01", "2024-02"],
            dtype="datetime64[M]",
        )

        ff = grid_to_feature_frame(
            grid, pgids, time_steps, ["a", "b"],
        )
        ff.save(tmp_path / "rt")
        loaded = FeatureFrame.load(tmp_path / "rt")
        reconstructed = feature_frame_to_grid(
            loaded, pgids
        )

        np.testing.assert_array_equal(grid, reconstructed)

    def test_roundtrip_sparse_grid(self) -> None:
        """Sparse grid (99% zeros) survives roundtrip."""
        grid = np.zeros(
            (3, 5, 6, 2), dtype=np.float32
        )
        grid[0, 1, 2, 0] = 5.0
        grid[2, 3, 4, 1] = 7.0
        pgids = np.arange(1, 31).reshape(5, 6)
        time_steps = np.array(
            ["2024-01", "2024-02", "2024-03"],
            dtype="datetime64[M]",
        )

        ff = grid_to_feature_frame(
            grid, pgids, time_steps, ["x", "y"],
        )
        reconstructed = feature_frame_to_grid(ff, pgids)

        np.testing.assert_array_equal(grid, reconstructed)

    def test_roundtrip_single_timestep(self) -> None:
        """Single time step roundtrip."""
        grid = np.ones(
            (1, 2, 3, 1), dtype=np.float32
        )
        pgids = np.arange(1, 7).reshape(2, 3)
        time_steps = np.array(
            ["2024-06"], dtype="datetime64[M]",
        )

        ff = grid_to_feature_frame(
            grid, pgids, time_steps, ["f"],
        )
        reconstructed = feature_frame_to_grid(ff, pgids)

        np.testing.assert_array_equal(grid, reconstructed)


# ---- Grid shape validation: Beige (C-73) ----


class TestGridShapeValidationBeige:

    def test_3d_grid_rejected(self) -> None:
        """3D grid [T, H*W, C] instead of 4D [T, H, W, C]."""
        grid_3d = np.zeros((2, 12, 2), dtype=np.float32)
        pgids = np.arange(1, 13).reshape(3, 4)
        time_steps = np.array(
            ["2024-01", "2024-02"],
            dtype="datetime64[M]",
        )
        with pytest.raises(ValueError, match="4D"):
            grid_to_dataframe(
                grid_3d, pgids, time_steps, ["a", "b"],
            )

    def test_transposed_grid_rejected(self) -> None:
        """Grid [T, W, H, C] with pgids [H, W] caught."""
        grid = np.zeros(
            (2, 4, 3, 2), dtype=np.float32,
        )  # W=4, H=3
        pgids = np.arange(1, 13).reshape(3, 4)  # H=3, W=4
        time_steps = np.array(
            ["2024-01", "2024-02"],
            dtype="datetime64[M]",
        )
        with pytest.raises(ValueError, match="spatial dims"):
            grid_to_dataframe(
                grid, pgids, time_steps, ["a", "b"],
            )

    def test_1d_pgids_rejected(self) -> None:
        """Flattened pgids should be rejected."""
        grid = np.zeros(
            (2, 3, 4, 2), dtype=np.float32,
        )
        pgids_flat = np.arange(1, 13)  # 1D
        time_steps = np.array(
            ["2024-01", "2024-02"],
            dtype="datetime64[M]",
        )
        with pytest.raises(ValueError, match="2D"):
            grid_to_dataframe(
                grid, pgids_flat, time_steps, ["a", "b"],
            )

    def test_grid_to_feature_frame_validates(self) -> None:
        """grid_to_feature_frame rejects bad shapes."""
        grid_3d = np.zeros((2, 12, 2), dtype=np.float32)
        pgids = np.arange(1, 13).reshape(3, 4)
        time_steps = np.array(
            ["2024-01", "2024-02"],
            dtype="datetime64[M]",
        )
        with pytest.raises(ValueError, match="4D"):
            grid_to_feature_frame(
                grid_3d, pgids, time_steps, ["a", "b"],
            )

    def test_feature_frame_to_grid_rejects_samples(
        self,
    ) -> None:
        """feature_frame_to_grid rejects S > 1."""
        index = SpatioTemporalIndex(
            time=np.arange(5, dtype=np.int64),
            unit=np.arange(5, dtype=np.int64),
            level=SpatialLevel.PGM,
        )
        ff = FeatureFrame(
            y_features=np.zeros(
                (5, 2, 3), dtype=np.float32
            ),
            index=index,
            feature_names=["a", "b"],
        )
        pgids = np.arange(1, 13).reshape(3, 4)
        with pytest.raises(ValueError, match="S=1"):
            feature_frame_to_grid(ff, pgids)

    def test_feature_frame_to_grid_1d_pgids(
        self,
    ) -> None:
        """feature_frame_to_grid rejects 1D pgids."""
        grid = np.zeros(
            (2, 3, 4, 2), dtype=np.float32,
        )
        pgids = np.arange(1, 13).reshape(3, 4)
        time_steps = np.array(
            ["2024-01", "2024-02"],
            dtype="datetime64[M]",
        )
        ff = grid_to_feature_frame(
            grid, pgids, time_steps, ["a", "b"],
        )
        with pytest.raises(ValueError, match="2D"):
            feature_frame_to_grid(ff, pgids.ravel())


class TestSharedValidation:
    """Direct tests for _validation.py shared helpers (C-112)."""

    def test_valid_grid_pgids(self) -> None:
        from datafactory_adapters._validation import (
            validate_grid_pgids,
        )

        grid = np.zeros((2, 3, 4, 2), dtype=np.float32)
        pgids = np.arange(12).reshape(3, 4)
        validate_grid_pgids(grid, pgids)  # should not raise

    def test_grid_not_4d(self) -> None:
        from datafactory_adapters._validation import (
            validate_grid_pgids,
        )

        grid = np.zeros((2, 12, 2), dtype=np.float32)
        pgids = np.arange(12).reshape(3, 4)
        with pytest.raises(ValueError, match="4D"):
            validate_grid_pgids(grid, pgids)

    def test_pgids_not_2d(self) -> None:
        from datafactory_adapters._validation import validate_pgids

        with pytest.raises(ValueError, match="2D"):
            validate_pgids(np.arange(12))

    def test_shape_mismatch(self) -> None:
        from datafactory_adapters._validation import (
            validate_grid_pgids,
        )

        grid = np.zeros((2, 3, 4, 2), dtype=np.float32)
        pgids = np.arange(12).reshape(4, 3)  # transposed
        with pytest.raises(ValueError, match="spatial dims"):
            validate_grid_pgids(grid, pgids)


# ---- views-frames conformance: Green (#221) ----


class TestViewsFramesConformance:
    """Run views-frames conformance suite against adapter output."""

    def test_grid_to_feature_frame_conforms(self) -> None:
        from views_frames.conformance import (
            assert_frame_contract,
        )

        grid = np.random.rand(2, 3, 4, 2).astype(
            np.float32
        )
        pgids = np.arange(1, 13).reshape(3, 4)
        time_steps = np.array(
            ["2024-01", "2024-02"],
            dtype="datetime64[M]",
        )
        ff = grid_to_feature_frame(
            grid, pgids, time_steps, ["count", "best"]
        )
        assert_frame_contract(ff)

    def test_direct_construction_conforms(self) -> None:
        from views_frames.conformance import (
            assert_frame_contract,
        )

        index = SpatioTemporalIndex(
            time=np.arange(10, dtype=np.int64),
            unit=np.arange(10, dtype=np.int64),
            level=SpatialLevel.PGM,
        )
        ff = FeatureFrame.from_2d(
            y_features_2d=np.random.rand(10, 3).astype(
                np.float32
            ),
            index=index,
            feature_names=["a", "b", "c"],
        )
        assert_frame_contract(ff)
