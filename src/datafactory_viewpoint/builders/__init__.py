"""Pluggable viewpoint builder registry.

Each builder module registers itself via register_builder().
Consumers call build_viewpoint(name, ...) without knowing the implementation.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

_BUILDERS: dict[str, Callable[..., Any]] = {}


def register_builder(name: str, build_fn: Callable[..., Any]) -> None:
    """Register a viewpoint builder function.

    Args:
        name: Builder identifier (e.g., "ucdp_v1").
        build_fn: Callable that builds a viewpoint from consolidated data.
    """
    _BUILDERS[name] = build_fn
    logger.info("Registered viewpoint builder: %s", name)


def build_viewpoint(name: str, **kwargs: Any) -> Any:
    """Build a viewpoint using a registered builder.

    Args:
        name: Builder identifier.
        **kwargs: Passed to the builder function.

    Raises:
        KeyError: If the builder name is not registered.
    """
    if name not in _BUILDERS:
        available = sorted(_BUILDERS.keys())
        err_msg = (
            f"Unknown viewpoint builder '{name}'. "
            f"Available: {available or 'none registered'}"
        )
        logger.error(err_msg)
        raise KeyError(err_msg)
    return _BUILDERS[name](**kwargs)


def list_builders() -> list[str]:
    """Return sorted list of registered builder names."""
    return sorted(_BUILDERS.keys())


def _clear_registry() -> None:
    """Clear all registered builders. For test isolation only."""
    _BUILDERS.clear()
