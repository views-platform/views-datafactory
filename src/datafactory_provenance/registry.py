"""Generic function registry for pluggable components.

Replaces 6 identical dict-based registries (C-80) with a single
reusable class. Supports both explicit registration and decorator
registration. See ADR-020 for the concern that motivated this.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Generic, TypeVar

T = TypeVar("T", bound=Callable[..., object])


class Registry(Generic[T]):
    """Named registry of callable objects.

    Provides registration (explicit or decorator), lookup, listing,
    and test-isolation clearing. Used by harvester sources,
    consolidators, viewpoint builders, and strategy registries.

    Example (explicit registration)::

        _registry = Registry[Callable[..., Any]]("data source")
        _registry.register("ucdp_annual", fetch_ucdp_annual)
        fn = _registry.get("ucdp_annual")

    Example (decorator registration)::

        _registry = Registry[Callable[[list[dict]], float]]("strategy")

        @_registry.decorator("count")
        def count(events: list[dict]) -> float:
            return float(len(events))
    """

    def __init__(self, kind: str) -> None:
        self._kind = kind
        self._entries: dict[str, T] = {}
        self._logger = logging.getLogger(
            f"{__name__}.{kind.replace(' ', '_')}"
        )

    def register(self, name: str, fn: T) -> None:
        """Register a callable by name."""
        self._entries[name] = fn
        self._logger.info(
            "Registered %s: %s", self._kind, name
        )

    def decorator(self, name: str) -> Callable[[T], T]:
        """Decorator factory for registration."""
        def wrapper(fn: T) -> T:
            self.register(name, fn)
            return fn
        return wrapper

    def get(self, name: str) -> T:
        """Look up a registered callable by name.

        Raises:
            KeyError: If the name is not registered. Message
                lists available entries.
        """
        if name not in self._entries:
            available = sorted(self._entries.keys())
            err_msg = (
                f"Unknown {self._kind} '{name}'. "
                f"Available: {available or 'none registered'}"
            )
            self._logger.error(err_msg)
            raise KeyError(err_msg)
        return self._entries[name]

    def list_entries(self) -> list[str]:
        """Return sorted list of registered names."""
        return sorted(self._entries.keys())

    def clear(self) -> None:
        """Remove all entries. For test isolation only."""
        self._entries.clear()

    @property
    def entries(self) -> dict[str, T]:
        """Direct access to the underlying dict.

        Exposed for backward-compatible test fixtures that
        manipulate the dict directly.
        """
        return self._entries
