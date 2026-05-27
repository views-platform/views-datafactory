"""Pluggable consolidator registry.

Each consolidator module registers itself via register_consolidator().
Consumers call consolidate_source(name, ...) without knowing the implementation.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

__all__ = ["consolidate_source", "list_consolidators", "register_consolidator"]

from datafactory_provenance.registry import Registry

_registry: Registry[Callable[..., Any]] = Registry("consolidator")

register_consolidator = _registry.register
list_consolidators = _registry.list_entries


def consolidate_source(name: str, **kwargs: Any) -> Any:
    """Consolidate data from a registered source.

    Args:
        name: Consolidator identifier.
        **kwargs: Passed to the consolidator function.

    Raises:
        KeyError: If the consolidator name is not registered.
    """
    return _registry.get(name)(**kwargs)
