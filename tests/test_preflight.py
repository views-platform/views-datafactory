"""Tests for compilation pre-flight resource checks.

Green: estimate_grid_bytes correctness, check_disk_space passes.
Beige: custom margin, default parameters.
Red: insufficient disk raises with actionable message.

Ref: ADR-037 (bounded-memory compilation), C-223.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from datafactory_compilation.preflight import (
    check_disk_space,
    estimate_grid_bytes,
)

# ---- Green ----


class TestEstimateGridBytesGreen:

    def test_single_feature(self) -> None:
        result = estimate_grid_bytes(
            n_months=12, n_features=1,
        )
        assert result == 12 * 360 * 720 * 1 * 4

    def test_multiple_features(self) -> None:
        result = estimate_grid_bytes(
            n_months=12, n_features=22,
        )
        assert result == 12 * 360 * 720 * 22 * 4

    def test_custom_grid_dimensions(self) -> None:
        result = estimate_grid_bytes(
            n_months=6, n_features=2,
            height=2, width=4, dtype_bytes=8,
        )
        assert result == 6 * 2 * 4 * 2 * 8

    def test_matches_manual_calculation(self) -> None:
        n_months, n_features = 552, 22
        manual = n_months * 360 * 720 * n_features * 4
        assert estimate_grid_bytes(n_months, n_features) == manual


class TestCheckDiskSpaceGreen:

    def test_passes_when_sufficient(self, tmp_path: Path) -> None:
        check_disk_space(tmp_path, required_bytes=1024)

    def test_passes_with_exact_margin(
        self, tmp_path: Path,
    ) -> None:
        mock_usage = type(
            "usage", (), {"total": 100, "used": 0, "free": 120},
        )()
        with patch("shutil.disk_usage", return_value=mock_usage):
            check_disk_space(
                tmp_path, required_bytes=100, margin=1.2,
            )


# ---- Beige ----


class TestCheckDiskSpaceBeige:

    def test_custom_margin(self, tmp_path: Path) -> None:
        mock_usage = type(
            "usage", (),
            {"total": 200, "used": 0, "free": 200},
        )()
        with patch("shutil.disk_usage", return_value=mock_usage):
            check_disk_space(
                tmp_path, required_bytes=100, margin=2.0,
            )

    def test_default_margin_is_1_2(self, tmp_path: Path) -> None:
        mock_usage = type(
            "usage", (),
            {"total": 200, "used": 80, "free": 119},
        )()
        with (
            patch("shutil.disk_usage", return_value=mock_usage),
            pytest.raises(RuntimeError),
        ):
            check_disk_space(tmp_path, required_bytes=100)

    def test_zero_bytes_always_passes(
        self, tmp_path: Path,
    ) -> None:
        check_disk_space(tmp_path, required_bytes=0)


# ---- Red ----


class TestCheckDiskSpaceRed:

    def test_raises_when_insufficient(
        self, tmp_path: Path,
    ) -> None:
        mock_usage = type(
            "usage", (),
            {"total": 100, "used": 100, "free": 0},
        )()
        with (
            patch("shutil.disk_usage", return_value=mock_usage),
            pytest.raises(
                RuntimeError, match="Insufficient disk"
            ),
        ):
            check_disk_space(tmp_path, required_bytes=1000)

    def test_error_message_includes_gb_values(
        self, tmp_path: Path,
    ) -> None:
        free_bytes = 500_000_000
        mock_usage = type(
            "usage", (),
            {"total": 10**10, "used": 0, "free": free_bytes},
        )()
        with (
            patch("shutil.disk_usage", return_value=mock_usage),
            pytest.raises(RuntimeError, match=r"\d+\.\d+ GB"),
        ):
            check_disk_space(
                tmp_path, required_bytes=10_000_000_000,
            )

    def test_error_message_is_actionable(
        self, tmp_path: Path,
    ) -> None:
        mock_usage = type(
            "usage", (),
            {"total": 100, "used": 100, "free": 0},
        )()
        with (
            patch("shutil.disk_usage", return_value=mock_usage),
            pytest.raises(
                RuntimeError, match="Free up space"
            ),
        ):
            check_disk_space(tmp_path, required_bytes=1000)
