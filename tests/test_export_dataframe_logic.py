"""Tests for export logic in export_dataframe.py.

Addresses C-102: no tests for dataframe export. Tests sparse vs
dense modes, month_id epoch encoding, and empty grid handling.
Most conversion logic is already tested in test_adapters.py —
these tests cover the script-level integration points.
"""

from __future__ import annotations

import numpy as np

from datafactory_adapters import grid_to_dataframe


class TestSparseVsDense:
    """Sparse and dense DataFrame export modes."""

    def test_dense_has_all_land_cells(self) -> None:
        """Dense mode: rows = land_cells * months."""
        n_t, n_h, n_w, n_c = 2, 3, 4, 1
        grid = np.zeros(
            (n_t, n_h, n_w, n_c), dtype=np.float32
        )
        grid[0, 1, 1, 0] = 5.0  # one non-zero cell
        pgids = np.arange(1, 13).reshape(n_h, n_w)
        time_steps = np.arange(
            "2023-01", "2023-03", dtype="datetime64[M]"
        )
        land_pgids = {1, 2, 5, 6}  # 4 land cells

        df = grid_to_dataframe(
            grid, pgids, time_steps, ["count"],
            land_pgids=land_pgids,
            sparse=False,
        )
        assert len(df) == 4 * 2  # 4 cells * 2 months

    def test_sparse_fewer_rows_than_dense(self) -> None:
        """Sparse mode produces fewer rows when grid is mostly zero."""
        n_t, n_h, n_w, n_c = 2, 3, 4, 1
        grid = np.zeros(
            (n_t, n_h, n_w, n_c), dtype=np.float32
        )
        grid[0, 1, 1, 0] = 5.0
        pgids = np.arange(1, 13).reshape(n_h, n_w)
        time_steps = np.arange(
            "2023-01", "2023-03", dtype="datetime64[M]"
        )

        df_sparse = grid_to_dataframe(
            grid, pgids, time_steps, ["count"],
            sparse=True,
        )
        df_dense = grid_to_dataframe(
            grid, pgids, time_steps, ["count"],
            land_pgids=set(pgids.ravel()),
            sparse=False,
        )
        assert len(df_sparse) < len(df_dense)
        assert len(df_sparse) == 1  # only one non-zero cell-month

    def test_empty_grid_sparse_produces_zero_rows(self) -> None:
        """All-zero grid in sparse mode → empty DataFrame."""
        grid = np.zeros((2, 3, 4, 1), dtype=np.float32)
        pgids = np.arange(1, 13).reshape(3, 4)
        time_steps = np.arange(
            "2023-01", "2023-03", dtype="datetime64[M]"
        )

        df = grid_to_dataframe(
            grid, pgids, time_steps, ["count"],
            sparse=True,
        )
        assert len(df) == 0
        assert list(df.columns) == ["count"]


class TestMonthIdEpoch:
    """Month ID encoding with different epoch offsets."""

    def test_epoch_zero_gives_raw_encoding(self) -> None:
        """epoch=0: month_id = year*12 + month."""
        grid = np.ones((1, 1, 1, 1), dtype=np.float32)
        pgids = np.array([[1]])
        time_steps = np.array(
            ["2023-06"], dtype="datetime64[M]"
        )

        df = grid_to_dataframe(
            grid, pgids, time_steps, ["x"],
            sparse=True,
            month_id_epoch=0,
        )
        month_id = df.index.get_level_values("month_id")[0]
        # 2023*12 + 6 = 24282
        assert month_id == 24282

    def test_epoch_1980_gives_views_convention(self) -> None:
        """epoch=1980: month_id = (year-1980)*12 + month."""
        grid = np.ones((1, 1, 1, 1), dtype=np.float32)
        pgids = np.array([[1]])
        time_steps = np.array(
            ["2023-06"], dtype="datetime64[M]"
        )

        df = grid_to_dataframe(
            grid, pgids, time_steps, ["x"],
            sparse=True,
            month_id_epoch=1980,
        )
        month_id = df.index.get_level_values("month_id")[0]
        # (2023-1980)*12 + 6 = 522
        assert month_id == 522

    def test_different_epochs_differ_by_offset(self) -> None:
        """Two epochs differ by exactly (epoch_diff * 12)."""
        grid = np.ones((1, 1, 1, 1), dtype=np.float32)
        pgids = np.array([[1]])
        time_steps = np.array(
            ["2023-01"], dtype="datetime64[M]"
        )

        df_0 = grid_to_dataframe(
            grid, pgids, time_steps, ["x"],
            sparse=True,
            month_id_epoch=0,
        )
        df_1980 = grid_to_dataframe(
            grid, pgids, time_steps, ["x"],
            sparse=True,
            month_id_epoch=1980,
        )
        id_0 = df_0.index.get_level_values("month_id")[0]
        id_1980 = df_1980.index.get_level_values("month_id")[0]
        assert id_0 - id_1980 == 1980 * 12
