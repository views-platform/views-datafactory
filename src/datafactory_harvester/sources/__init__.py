"""Pluggable data source registry.

Each source module registers itself via register_source().
Consumers call fetch_source(name, ...) without knowing the implementation.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

_SOURCES: dict[str, Callable[..., Any]] = {}


def register_source(name: str, fetch_fn: Callable[..., Any]) -> None:
    """Register a data source fetch function.

    Args:
        name: Source identifier (e.g., "ucdp_annual").
        fetch_fn: Callable that fetches data. Return type varies by source.
    """
    _SOURCES[name] = fetch_fn
    logger.info("Registered data source: %s", name)


def fetch_source(name: str, **kwargs: Any) -> Any:
    """Fetch data from a registered source.

    Args:
        name: Source identifier.
        **kwargs: Passed to the source's fetch function.

    Returns:
        Source-specific result (Path for single-source, list[dict] for multi-version).

    Raises:
        KeyError: If the source name is not registered.
    """
    if name not in _SOURCES:
        available = sorted(_SOURCES.keys())
        err_msg = (
            f"Unknown source '{name}'. "
            f"Available: {available or 'none registered'}"
        )
        logger.error(err_msg)
        raise KeyError(err_msg)
    return _SOURCES[name](**kwargs)


def list_sources() -> list[str]:
    """Return sorted list of registered source names."""
    return sorted(_SOURCES.keys())
