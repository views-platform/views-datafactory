"""Pluggable data source registry.

Each source module registers itself via register_source().
Consumers call fetch_source(name, ...) without knowing the implementation.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from datafactory_provenance.registry import Registry

_registry: Registry[Callable[..., Any]] = Registry("source")

# Backward-compatible public API
_SOURCES = _registry.entries  # conftest.py accesses this directly
register_source = _registry.register
list_sources = _registry.list_entries


def fetch_source(name: str, **kwargs: Any) -> Any:
    """Fetch data from a registered source.

    Args:
        name: Source identifier.
        **kwargs: Passed to the source's fetch function.

    Returns:
        Source-specific result (Path for single-source,
        list[dict] for multi-version).

    Raises:
        KeyError: If the source name is not registered.
    """
    return _registry.get(name)(**kwargs)
