"""Survivorship strategy registry for viewpoint building.

Each strategy is a function: list[dict] -> dict.
Given all versions of the same event (same id, different source
versions), the strategy picks the winning record.

Adding a new strategy means adding a function here with the
@_register decorator — no changes to the builder (OCP).
"""

from __future__ import annotations

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

__all__ = ["get_survivorship", "annual_wins"]

STRATEGIES: dict[str, Callable[[list[dict]], dict]] = {}


def _register(name: str) -> Callable:
    """Decorator to register a survivorship strategy by name."""
    def decorator(
        fn: Callable[[list[dict]], dict],
    ) -> Callable[[list[dict]], dict]:
        STRATEGIES[name] = fn
        return fn
    return decorator


def get_survivorship(name: str) -> Callable[[list[dict]], dict]:
    """Look up a survivorship strategy by name.

    Raises:
        KeyError: If the strategy name is not registered.
    """
    if name not in STRATEGIES:
        available = sorted(STRATEGIES.keys())
        err_msg = (
            f"Unknown survivorship strategy '{name}'. "
            f"Available: {available}"
        )
        logger.error(err_msg)
        raise KeyError(err_msg)
    return STRATEGIES[name]


def _parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a version string into a tuple of ints for comparison.

    Examples: "25.1" → (25, 1), "25.0.12" → (25, 0, 12)
    """
    return tuple(int(p) for p in version_str.split("."))


@_register("annual_wins")
def annual_wins(versions: list[dict]) -> dict:
    """Pick annual if available, else latest candidate by version.

    Survivorship rule per ADR-015: annual is authoritative for
    months it covers. For the trailing window, the latest
    candidate version wins.
    """
    annuals = [
        v for v in versions if v.get("_source_type") == "annual"
    ]
    if annuals:
        # If multiple annual versions, pick the latest
        return max(annuals, key=lambda v: _parse_version(
            v.get("_source_version", "0")
        ))

    # No annual — pick latest candidate by version number
    return max(versions, key=lambda v: _parse_version(
        v.get("_source_version", "0")
    ))
