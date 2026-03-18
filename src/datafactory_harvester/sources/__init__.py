"""Pluggable data source registry.

Each source module registers itself via register_source().
Consumers call fetch_source(name, ...) without knowing the implementation.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SOURCES: dict[str, Callable[..., Path]] = {}


def register_source(name: str, fetch_fn: Callable[..., Path]) -> None:
    """Register a data source fetch function.

    Args:
        name: Source identifier (e.g., "ucdp_annual").
        fetch_fn: Callable that fetches data and returns the snapshot path.
    """
    _SOURCES[name] = fetch_fn
    logger.info("Registered data source: %s", name)


def fetch_source(name: str, **kwargs: Any) -> Path:
    """Fetch data from a registered source.

    Args:
        name: Source identifier.
        **kwargs: Passed to the source's fetch function.

    Returns:
        Path to the fetched data snapshot.

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
