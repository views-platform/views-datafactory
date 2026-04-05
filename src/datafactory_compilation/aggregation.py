"""Built-in aggregation strategies for grid compilation.

Each strategy is a plain function: list[dict] -> float.
Strategies aggregate events within a single (cell, month) bin.
Adding a new strategy means adding a function here -- no changes
to the compiler or config modules (OCP).
"""

from __future__ import annotations

from collections.abc import Callable

from datafactory_provenance.registry import Registry

_registry: Registry[Callable[[list[dict]], float]] = Registry(
    "aggregation strategy"
)
STRATEGIES = _registry.entries


@_registry.decorator("count")
def count(events: list[dict]) -> float:
    """Count of events in this cell-month."""
    return float(len(events))


@_registry.decorator("sum_best")
def sum_best(events: list[dict]) -> float:
    """Sum of 'best' fatality estimates in this cell-month."""
    return float(sum(e.get("best", 0) or 0 for e in events))


@_registry.decorator("max_best")
def max_best(events: list[dict]) -> float:
    """Maximum 'best' fatality estimate in this cell-month."""
    values = [e.get("best", 0) or 0 for e in events]
    return float(max(values)) if values else 0.0


def get_strategy(name: str) -> Callable[[list[dict]], float]:
    """Look up a strategy by name.

    Raises:
        KeyError: If the strategy name is not registered.
    """
    return _registry.get(name)
