"""Tests for shared harvester config validation utilities."""

import pytest

from datafactory_harvester.validation import (
    validate_month,
    validate_nonempty_string,
    validate_positive_float,
    validate_positive_int,
    validate_string_tuple,
    validate_year_range,
)

# ── validate_positive_int ────────────────────────────────────────────


class TestValidatePositiveInt:
    """Green: normal values. Beige: edge cases. Red: invalid inputs."""

    def test_accepts_one(self) -> None:
        validate_positive_int(1, "timeout")

    def test_accepts_large_value(self) -> None:
        validate_positive_int(9999, "page_size")

    def test_rejects_zero(self) -> None:
        with pytest.raises(ValueError, match="timeout must be >= 1, got 0"):
            validate_positive_int(0, "timeout")

    def test_rejects_negative(self) -> None:
        with pytest.raises(ValueError, match="max_retries must be >= 1, got -5"):
            validate_positive_int(-5, "max_retries")

    def test_field_name_in_message(self) -> None:
        with pytest.raises(ValueError, match="page_size"):
            validate_positive_int(0, "page_size")


# ── validate_positive_float ──────────────────────────────────────────


class TestValidatePositiveFloat:

    def test_accepts_positive(self) -> None:
        validate_positive_float(0.5, "page_delay")

    def test_accepts_small_positive(self) -> None:
        validate_positive_float(0.001, "discovery_rate_limit")

    def test_rejects_zero(self) -> None:
        with pytest.raises(ValueError, match="page_delay must be > 0, got 0"):
            validate_positive_float(0, "page_delay")

    def test_rejects_negative(self) -> None:
        with pytest.raises(
            ValueError, match="discovery_rate_limit must be > 0"
        ):
            validate_positive_float(-1.0, "discovery_rate_limit")

    def test_field_name_in_message(self) -> None:
        with pytest.raises(ValueError, match="page_delay"):
            validate_positive_float(0, "page_delay")


# ── validate_nonempty_string ─────────────────────────────────────────


class TestValidateNonemptyString:

    def test_accepts_nonempty(self) -> None:
        validate_nonempty_string("v14", "version")

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="version must be non-empty"):
            validate_nonempty_string("", "version")

    def test_field_name_in_message(self) -> None:
        with pytest.raises(ValueError, match="version"):
            validate_nonempty_string("", "version")


# ── validate_string_tuple ────────────────────────────────────────────


class TestValidateStringTuple:

    def test_accepts_valid_tuple(self) -> None:
        validate_string_tuple(("shdi", "healthindex", "edindex"), "variables")

    def test_accepts_single_element(self) -> None:
        validate_string_tuple(("shdi",), "variables")

    def test_rejects_empty_tuple(self) -> None:
        with pytest.raises(ValueError, match="variables must be non-empty"):
            validate_string_tuple((), "variables")

    def test_rejects_empty_string_element(self) -> None:
        with pytest.raises(
            ValueError, match="variables must not contain empty strings"
        ):
            validate_string_tuple(("shdi", ""), "variables")

    def test_rejects_duplicate(self) -> None:
        with pytest.raises(ValueError, match="duplicate variable: shdi"):
            validate_string_tuple(("shdi", "shdi"), "variables")

    def test_duplicate_message_uses_singular(self) -> None:
        with pytest.raises(ValueError, match="duplicate variable"):
            validate_string_tuple(("a", "b", "a"), "variables")


# ── validate_month ───────────────────────────────────────────────────


class TestValidateMonth:

    def test_accepts_january(self) -> None:
        validate_month(1, "start_month")

    def test_accepts_december(self) -> None:
        validate_month(12, "start_month")

    def test_accepts_mid_year(self) -> None:
        validate_month(6, "start_month")

    def test_rejects_zero(self) -> None:
        with pytest.raises(
            ValueError, match="start_month must be in \\[1, 12\\], got 0"
        ):
            validate_month(0, "start_month")

    def test_rejects_thirteen(self) -> None:
        with pytest.raises(ValueError, match="start_month must be in"):
            validate_month(13, "start_month")

    def test_rejects_negative(self) -> None:
        with pytest.raises(ValueError, match="start_month must be in"):
            validate_month(-1, "start_month")


# ── validate_year_range ──────────────────────────────────────────────


class TestValidateYearRange:

    def test_accepts_equal_years(self) -> None:
        validate_year_range(2020, 2020)

    def test_accepts_ascending_range(self) -> None:
        validate_year_range(2010, 2025)

    def test_rejects_descending_range(self) -> None:
        with pytest.raises(
            ValueError,
            match="end_year \\(2019\\) must be >= start_year \\(2020\\)",
        ):
            validate_year_range(2020, 2019)
