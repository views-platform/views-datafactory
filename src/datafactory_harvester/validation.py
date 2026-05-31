"""Shared config validation utilities for harvester dataclasses.

Each function raises ``ValueError`` with a descriptive message on
invalid input.  Designed for use in ``__post_init__`` of frozen
dataclasses — call the relevant validators instead of writing
inline ``if … raise`` blocks.
"""

from __future__ import annotations

__all__ = [
    "validate_month",
    "validate_nonempty_string",
    "validate_positive_float",
    "validate_positive_int",
    "validate_string_tuple",
    "validate_year_range",
]


def validate_positive_int(value: int, name: str) -> None:
    """Raise if *value* < 1."""
    if value < 1:
        msg = f"{name} must be >= 1, got {value}"
        raise ValueError(msg)


def validate_positive_float(value: float, name: str) -> None:
    """Raise if *value* <= 0."""
    if value <= 0:
        msg = f"{name} must be > 0, got {value}"
        raise ValueError(msg)


def validate_nonempty_string(value: str, name: str) -> None:
    """Raise if *value* is empty."""
    if not value:
        msg = f"{name} must be non-empty"
        raise ValueError(msg)


def validate_string_tuple(
    values: tuple[str, ...], name: str,
) -> None:
    """Raise if *values* is empty, contains empty strings, or has duplicates."""
    if not values:
        msg = f"{name} must be non-empty"
        raise ValueError(msg)
    seen: set[str] = set()
    for v in values:
        if not v:
            msg = f"{name} must not contain empty strings"
            raise ValueError(msg)
        if v in seen:
            msg = f"duplicate variable: {v}"
            raise ValueError(msg)
        seen.add(v)


def validate_month(value: int, name: str) -> None:
    """Raise if *value* not in [1, 12]."""
    if not (1 <= value <= 12):
        msg = f"{name} must be in [1, 12], got {value}"
        raise ValueError(msg)


def validate_year_range(start_year: int, end_year: int) -> None:
    """Raise if *end_year* < *start_year*."""
    if end_year < start_year:
        msg = (
            f"end_year ({end_year}) must be >= "
            f"start_year ({start_year})"
        )
        raise ValueError(msg)
