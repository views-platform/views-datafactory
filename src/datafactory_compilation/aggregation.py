"""Built-in aggregation strategies for grid compilation.

Each strategy is a plain function: (list[dict], str) -> float.
Strategies aggregate events within a single (cell, month) bin.
The second argument is the event field name to aggregate.
Adding a new strategy means adding a function here -- no changes
to the compiler or config modules (OCP).
"""

from __future__ import annotations

from collections.abc import Callable

from datafactory_provenance.registry import Registry

__all__ = [
    "count",
    "sum_field",
    "max_field",
    "get_strategy",
]

_registry: Registry[Callable[[list[dict], str], float]] = Registry(
    "aggregation strategy"
)


@_registry.decorator("count")
def count(events: list[dict], field: str = "best") -> float:
    """Count of events in this cell-month."""
    return float(len(events))


@_registry.decorator("sum_field")
def sum_field(events: list[dict], field: str = "best") -> float:
    """Sum of field values in this cell-month."""
    return float(sum(e.get(field, 0) or 0 for e in events))


@_registry.decorator("max_field")
def max_field(events: list[dict], field: str = "best") -> float:
    """Maximum field value in this cell-month."""
    values = [e.get(field, 0) or 0 for e in events]
    return float(max(values)) if values else 0.0


# Backward-compatible aliases — old registry keys still resolve
_registry.register("sum_best", sum_field)
_registry.register("max_best", max_field)

# Backward-compatible Python names
sum_best = sum_field
max_best = max_field


def get_strategy(
    name: str,
) -> Callable[[list[dict], str], float]:
    """Look up a strategy by name.

    Raises:
        KeyError: If the strategy name is not registered.
    """
    return _registry.get(name)
