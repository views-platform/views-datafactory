"""Pluggable viewpoint builder registry.

Each builder module registers itself via register_builder().
Consumers call build_viewpoint(name, ...) without knowing the implementation.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

__all__ = ["build_viewpoint", "list_builders", "register_builder"]

from datafactory_provenance.registry import Registry

_registry: Registry[Callable[..., Any]] = Registry("viewpoint builder")

register_builder = _registry.register
list_builders = _registry.list_entries
_clear_registry = _registry.clear


def build_viewpoint(name: str, **kwargs: Any) -> Any:
    """Build a viewpoint using a registered builder.

    Args:
        name: Builder identifier.
        **kwargs: Passed to the builder function.

    Raises:
        KeyError: If the builder name is not registered.
    """
    return _registry.get(name)(**kwargs)
