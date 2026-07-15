"""Tests for scripts/verify_consumer_contract.py (#323).

The check functions are pure — tested against synthetic monthly
sums with no network. The two incident-shaped cases (C-313 stale
source, C-314 spike) are the reason this script exists.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np

_SPEC = importlib.util.spec_from_file_location(
    "verify_consumer_contract",
    Path(__file__).parent.parent
    / "scripts" / "verify_consumer_contract.py",
)
vcc = importlib.util.module_from_spec(_SPEC)
sys.modules["verify_consumer_contract"] = vcc
_SPEC.loader.exec_module(vcc)


def _mid(year: int, month: int) -> int:
    return (year - 1980) * 12 + month


NOW = _mid(2026, 7)


class TestFreshnessGreen:

    def test_fresh_source_passes(self) -> None:
        """Nonzero data one month ago → no failure."""
        sums = {NOW - i: 1000.0 for i in range(1, 13)}
        assert vcc.check_freshness(
            sums, "acled_fatalities", 3, NOW,
        ) is None

    def test_within_slo_boundary_passes(self) -> None:
        """Last nonzero exactly at the SLO edge → no failure."""
        sums = {NOW - 3: 1000.0, NOW - 2: 0.0, NOW - 1: 0.0}
        assert vcc.check_freshness(
            sums, "acled_fatalities", 3, NOW,
        ) is None


class TestFreshnessRed:
    """C-313 shape: a source goes silent while others continue."""

    def test_stale_source_fails_naming_it(self) -> None:
        """ACLED zero after 2025-12, checked in 2026-07 → FAIL.

        This is exactly the state consumers saw on 2026-07-05
        before v1.6.3: pipeline green, ACLED 2026 all zeros.
        """
        sums = {
            _mid(2025, m): 20_000.0 for m in range(1, 13)
        }
        sums.update(
            {_mid(2026, m): 0.0 for m in range(1, 7)}
        )
        fail = vcc.check_freshness(
            sums, "acled_fatalities", 3, NOW,
        )
        assert fail is not None
        assert "acled_fatalities" in fail
        assert "2025-12" in fail

    def test_all_zero_window_fails(self) -> None:
        sums = {NOW - i: 0.0 for i in range(1, 13)}
        fail = vcc.check_freshness(
            sums, "ged_sb_best", 4, NOW,
        )
        assert fail is not None
        assert "no nonzero" in fail


class TestPlausibility:
    """C-314 shape: one enormous month → warn, never fail."""

    def test_spike_month_warns(self) -> None:
        """A 4x month is flagged with a warning string."""
        sums = {NOW - i: 20_000.0 for i in range(1, 13)}
        sums[NOW - 6] = 80_000.0
        warnings = vcc.check_plausibility(
            sums, "acled_fatalities",
        )
        assert len(warnings) == 1
        assert "80,000" in warnings[0]

    def test_normal_months_no_warning(self) -> None:
        sums = {
            NOW - i: 20_000.0 + 1_000.0 * (i % 5)
            for i in range(1, 13)
        }
        assert vcc.check_plausibility(
            sums, "acled_fatalities",
        ) == []

    def test_floor_guards_near_zero_baseline(self) -> None:
        """Iran lesson (#320): median 17 must not make every small
        wiggle a warning — the floor absorbs near-zero baselines."""
        sums = {NOW - i: 17.0 for i in range(1, 13)}
        sums[NOW - 2] = 900.0  # 53x the median, but under floor*3
        assert vcc.check_plausibility(
            sums, "ged_os_best",
        ) == []

    def test_true_mass_event_still_warns_over_floor(self) -> None:
        """A genuinely enormous month clears even the floor."""
        sums = {NOW - i: 17.0 for i in range(1, 13)}
        sums[NOW - 2] = 27_657.0  # the real Jan-2026 value
        warnings = vcc.check_plausibility(
            sums, "ged_os_best",
        )
        assert len(warnings) == 1

    def test_short_window_no_warnings(self) -> None:
        assert vcc.check_plausibility(
            {NOW - 1: 5.0, NOW - 2: 5.0}, "x",
        ) == []


class TestPresence:

    def test_present_feature_passes(self) -> None:
        sums = {NOW - 1: 0.0, NOW - 2: 42.0}
        assert vcc.check_presence(sums, "shdi_shdi") is None

    def test_absent_feature_fails(self) -> None:
        sums = {NOW - 1: 0.0, NOW - 2: 0.0}
        fail = vcc.check_presence(sums, "shdi_shdi")
        assert fail is not None
        assert "shdi_shdi" in fail


class TestHelpers:

    def test_month_id_round_trip(self) -> None:
        assert vcc.month_id_str(_mid(2026, 1)) == "2026-01"
        assert vcc.month_id_str(_mid(1989, 12)) == "1989-12"

    def test_monthly_sums_nansum(self) -> None:
        times = np.array([553, 553, 554])
        col = np.array([1.0, np.nan, 3.0])
        assert vcc.monthly_sums(times, col) == {
            553: 1.0, 554: 3.0,
        }

    def test_largest_jump_reports_biggest_delta(self) -> None:
        sums = {553: 100.0, 554: 100.0, 555: 5_000.0}
        info = vcc.largest_jump(sums, "f")
        assert info is not None
        assert "4,900" in info
