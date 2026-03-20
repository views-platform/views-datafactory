"""Pluggable consolidator registry.

Each consolidator module registers itself via register_consolidator().
Consumers call consolidate_source(name, ...) without knowing the implementation.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

_CONSOLIDATORS: dict[str, Callable[..., Any]] = {}


def register_consolidator(name: str, consolidate_fn: Callable[..., Any]) -> None:
    """Register a source-specific consolidation function.

    Args:
        name: Consolidator identifier (e.g., "ucdp").
        consolidate_fn: Callable that consolidates source snapshots.
    """
    _CONSOLIDATORS[name] = consolidate_fn
    logger.info("Registered consolidator: %s", name)


def consolidate_source(name: str, **kwargs: Any) -> Any:
    """Consolidate data from a registered source.

    Args:
        name: Consolidator identifier.
        **kwargs: Passed to the consolidator function.

    Raises:
        KeyError: If the consolidator name is not registered.
    """
    if name not in _CONSOLIDATORS:
        available = sorted(_CONSOLIDATORS.keys())
        err_msg = (
            f"Unknown consolidator '{name}'. "
            f"Available: {available or 'none registered'}"
        )
        logger.error(err_msg)
        raise KeyError(err_msg)
    return _CONSOLIDATORS[name](**kwargs)


def list_consolidators() -> list[str]:
    """Return sorted list of registered consolidator names."""
    return sorted(_CONSOLIDATORS.keys())


def _clear_registry() -> None:
    """Clear all registered consolidators. For test isolation only."""
    _CONSOLIDATORS.clear()
