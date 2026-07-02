"""Tests for DGP (data-generating process) validation (C-257, #212).

Tests the framework function validate_dgp_assumptions() and
source-specific DGP check functions for ACLED and UCDP.
"""

from __future__ import annotations

import pytest

# ---- Framework tests ----


class TestValidateDgpAssumptions:
    """Framework-level tests for validate_dgp_assumptions()."""

    def test_valid_events_zero_violations(self) -> None:
        """All checks return None → no exception raised."""
        from datafactory_harvester.event_validation import (
            validate_dgp_assumptions,
        )

        events = [{"x": 1}, {"x": 2}]
        checks = [lambda e: None, lambda e: None]
        validate_dgp_assumptions(events, checks, source_name="test")

    def test_single_violation_raises_valueerror(self) -> None:
        """One check returns a violation string → ValueError."""
        from datafactory_harvester.event_validation import (
            validate_dgp_assumptions,
        )

        events = [{"x": 1}]
        checks = [lambda e: "bad value"]
        with pytest.raises(ValueError, match="bad value"):
            validate_dgp_assumptions(
                events, checks, source_name="test",
            )

    def test_multiple_violations_all_reported(self) -> None:
        """Multiple checks fail → error message contains all."""
        from datafactory_harvester.event_validation import (
            validate_dgp_assumptions,
        )

        events = [{"x": 1}]
        checks = [
            lambda e: "violation-A",
            lambda e: "violation-B",
        ]
        with pytest.raises(ValueError) as exc_info:
            validate_dgp_assumptions(
                events, checks, source_name="test",
            )

        msg = str(exc_info.value)
        assert "violation-A" in msg
        assert "violation-B" in msg

    def test_violation_raises_valueerror_type(self) -> None:
        """Explicit isinstance check on raised exception."""
        from datafactory_harvester.event_validation import (
            validate_dgp_assumptions,
        )

        events = [{"x": -1}]
        checks = [lambda e: "negative x"]
        with pytest.raises(ValueError) as exc_info:
            validate_dgp_assumptions(
                events, checks, source_name="test",
            )
        assert isinstance(exc_info.value, ValueError)

    def test_warn_only_logs_instead_of_raising(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """warn_only=True → warning logged, no exception."""
        import logging

        from datafactory_harvester.event_validation import (
            validate_dgp_assumptions,
        )

        events = [{"x": 1}]
        checks = [lambda e: "known quirk"]
        with caplog.at_level(logging.WARNING):
            validate_dgp_assumptions(
                events, checks, source_name="test",
                warn_only=True,
            )
        assert "known quirk" in caplog.text
        assert "1 violation(s)" in caplog.text

    def test_warn_only_no_violations_no_warning(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """warn_only=True with clean events → silence."""
        import logging

        from datafactory_harvester.event_validation import (
            validate_dgp_assumptions,
        )

        events = [{"x": 1}]
        checks = [lambda e: None]
        with caplog.at_level(logging.WARNING):
            validate_dgp_assumptions(
                events, checks, source_name="test",
                warn_only=True,
            )
        assert "violation" not in caplog.text


# ---- ACLED DGP check tests ----


class TestAcledDgpChecks:
    """Unit tests for individual ACLED DGP check functions."""

    def test_acled_negative_fatalities_flagged(self) -> None:
        """fatalities=-1 → violation returned."""
        from datafactory_harvester.sources.acled import (
            _check_fatality_non_negative,
        )

        result = _check_fatality_non_negative({"fatalities": -1})
        assert result is not None
        assert "fatalit" in result.lower()

    def test_acled_unknown_event_type_flagged(self) -> None:
        """event_type='Unknown' → violation returned."""
        from datafactory_harvester.sources.acled import (
            _check_known_event_type,
        )

        result = _check_known_event_type(
            {"event_type": "Unknown"},
        )
        assert result is not None

    def test_acled_valid_event_passes(self) -> None:
        """Valid ACLED event → all checks return None."""
        from datafactory_harvester.sources.acled import (
            ACLED_DGP_CHECKS,
        )

        event = {
            "fatalities": 5,
            "event_type": "Battles",
            "latitude": "12.5",
            "longitude": "31.0",
        }
        violations = [c(event) for c in ACLED_DGP_CHECKS]
        assert all(v is None for v in violations)


# ---- UCDP DGP check tests ----


class TestUcdpDgpChecks:
    """Unit tests for individual UCDP DGP check functions."""

    def test_ucdp_date_prec_6_flagged(self) -> None:
        """date_prec=6 → violation returned."""
        from datafactory_harvester.sources.ucdp_annual import (
            _check_date_prec_range,
        )

        result = _check_date_prec_range({"date_prec": 6})
        assert result is not None

    def test_ucdp_low_exceeds_best_flagged(self) -> None:
        """low=10, best=5 → violation returned."""
        from datafactory_harvester.sources.ucdp_annual import (
            _check_best_high_low_ordering,
        )

        result = _check_best_high_low_ordering(
            {"low": 10, "best": 5, "high": 20},
        )
        assert result is not None

    def test_ucdp_valid_event_passes(self) -> None:
        """Valid UCDP event → all checks return None."""
        from datafactory_harvester.sources.ucdp_annual import (
            UCDP_DGP_CHECKS,
        )

        event = {
            "date_prec": 3,
            "type_of_violence": 2,
            "latitude": 12.5,
            "longitude": 31.0,
            "low": 1,
            "best": 5,
            "high": 10,
        }
        violations = [c(event) for c in UCDP_DGP_CHECKS]
        assert all(v is None for v in violations)

    def test_ordering_check_is_warn_not_fail(self) -> None:
        """best/high/low ordering is a warn check, not a hard check.

        Published UCDP data violates the ordering in ~1.3% of
        events (v25.1: 3,594 best>high + 1,415 low>best). A hard
        check here blocked the v26.1 harvest on 2026-07-02.
        """
        from datafactory_harvester.sources.ucdp_annual import (
            UCDP_DGP_CHECKS,
            UCDP_DGP_WARN_CHECKS,
            _check_best_high_low_ordering,
        )

        assert _check_best_high_low_ordering not in UCDP_DGP_CHECKS
        assert _check_best_high_low_ordering in UCDP_DGP_WARN_CHECKS

    def test_real_world_ordering_violation_does_not_block(self) -> None:
        """Event with best=11, high=0 (real v26.1 case) passes
        the hard checks — only the warn set flags it."""
        from datafactory_harvester.sources.ucdp_annual import (
            UCDP_DGP_CHECKS,
        )

        event = {
            "date_prec": 3,
            "type_of_violence": 1,
            "latitude": 12.5,
            "longitude": 31.0,
            "low": 0,
            "best": 11,
            "high": 0,
        }
        violations = [c(event) for c in UCDP_DGP_CHECKS]
        assert all(v is None for v in violations)
