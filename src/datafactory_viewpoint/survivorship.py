"""Survivorship strategy registry for viewpoint building.

Each strategy is a function: list[dict] -> dict.
Given all versions of the same event (same id, different source
versions), the strategy picks the winning record.

Adding a new strategy means adding a function here with the
@_registry.decorator — no changes to the builder (OCP).
"""

from __future__ import annotations

from collections.abc import Callable

from datafactory_provenance.registry import Registry

_registry: Registry[Callable[[list[dict]], dict]] = Registry(
    "survivorship strategy"
)
STRATEGIES = _registry.entries

__all__ = ["get_survivorship", "annual_wins", "dot9_wins"]


def get_survivorship(name: str) -> Callable[[list[dict]], dict]:
    """Look up a survivorship strategy by name.

    Raises:
        KeyError: If the strategy name is not registered.
    """
    return _registry.get(name)


def _parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a version string into a tuple of ints for comparison.

    Examples: "25.1" → (25, 1), "25.0.12" → (25, 0, 12)
    """
    return tuple(int(p) for p in version_str.split("."))


@_registry.decorator("annual_wins")
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


@_registry.decorator("dot9_wins")
def dot9_wins(versions: list[dict]) -> dict:
    """Annual > .9 > candidate. Production-parity survivorship.

    Prefers annual (authoritative, curated) when available.
    Falls back to .9 (UCDP's own consolidation with exclusive
    content). Last resort: latest individual candidate version.
    """
    annuals = [
        v for v in versions
        if v.get("_source_type") == "annual"
    ]
    if annuals:
        return max(annuals, key=lambda v: _parse_version(
            v.get("_source_version", "0")
        ))

    dot9s = [
        v for v in versions
        if v.get("_source_type") == "dot9"
    ]
    if dot9s:
        return max(dot9s, key=lambda v: _parse_version(
            v.get("_source_version", "0")
        ))

    return max(versions, key=lambda v: _parse_version(
        v.get("_source_version", "0")
    ))
