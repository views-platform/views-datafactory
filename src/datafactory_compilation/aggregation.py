"""Built-in aggregation strategies for grid compilation.

Each strategy is a plain function: list[dict] -> float.
Strategies aggregate events within a single (cell, month) bin.
Adding a new strategy means adding a function here -- no changes
to the compiler or config modules (OCP).
"""

from __future__ import annotations

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

# Strategy registry: name -> function
STRATEGIES: dict[str, Callable[[list[dict]], float]] = {}


def _register(name: str) -> Callable:
    """Decorator to register a strategy by name."""

    def decorator(fn: Callable[[list[dict]], float]) -> Callable[[list[dict]], float]:
        STRATEGIES[name] = fn
        return fn

    return decorator


@_register("count")
def count(events: list[dict]) -> float:
    """Count of events in this cell-month."""
    return float(len(events))


@_register("sum_best")
def sum_best(events: list[dict]) -> float:
    """Sum of 'best' fatality estimates in this cell-month."""
    return float(sum(e.get("best", 0) or 0 for e in events))


@_register("max_best")
def max_best(events: list[dict]) -> float:
    """Maximum 'best' fatality estimate in this cell-month."""
    values = [e.get("best", 0) or 0 for e in events]
    return float(max(values)) if values else 0.0


def get_strategy(name: str) -> Callable[[list[dict]], float]:
    """Look up a strategy by name.

    Raises:
        KeyError: If the strategy name is not registered.
    """
    if name not in STRATEGIES:
        available = sorted(STRATEGIES.keys())
        err_msg = (
            f"Unknown aggregation strategy '{name}'. "
            f"Available: {available}"
        )
        logger.error(err_msg)
        raise KeyError(err_msg)
    return STRATEGIES[name]
