"""Conserving integer apportionment of an extensive count across a support.

One rounder, used by every allocation strategy. Conservation (ADR-040
Invariant 1) is proved here once rather than re-argued per strategy, which
is the point of keeping it in its own module.

The rule is **largest remainder** (Hamilton apportionment): floor every
ideal share, then hand the integer shortfall to the largest fractional
remainders. Specified with its properties in
``reports/2026-11-04_summary_event_allocation_dossier/11_allocator_spec.md``.

Why not rank by weight. The previous in-place implementation inside
``spatial_distribution`` ranked by weight rather than by remainder. That
conserves, but it is not bounded: for ``v=10`` over weights
``(0.5, 0.25, 0.25)`` it returns ``(6, 2, 2)`` although the first cell's
ideal share is exactly ``5.0``. It also sends the remainder to the
already-largest cell every time, which is the concentration bias ADR-049
lists among its own negative consequences. Largest remainder returns
``(5, 3, 2)`` and cannot exceed any cell's ceiling.
"""

from __future__ import annotations

import math
from collections.abc import Hashable, Mapping
from typing import TypeVar

__all__ = ["apportion"]

K = TypeVar("K", bound=Hashable)


def apportion(total: int, weights: Mapping[K, float]) -> dict[K, int]:
    """Apportion *total* across *weights* by largest remainder.

    Args:
        total: Non-negative integer count to distribute. An extensive
            quantity (fatalities, event counts) -- see ADR-040 on the
            extensive/intensive distinction.
        weights: Support keys to non-negative weights. Need not sum to 1;
            they are normalised. Keys must be mutually comparable, because
            they are the deterministic tie-break (ADR-014 Principle 3).

    Returns:
        Keys to non-negative integers summing to exactly *total*. Keys
        with zero weight map to 0. Empty if *weights* is empty.

    Raises:
        ValueError: *total* negative, or any weight negative, NaN, or
            infinite, or all weights zero while *total* > 0. Fail loud
            rather than silently normalise away a broken cascade
            (ADR-011).

    Guarantees, each covered by a test in
    ``tests/test_apportionment.py``:

    - **P1 conservation** -- ``sum(result.values()) == total`` exactly.
    - **P2 boundedness** -- each allocation is ``floor`` or ``ceil`` of its
      ideal share ``total * w / sum(w)``.
    - **P3 determinism** -- identical input gives identical output; no
      entropy, so these allocators stay pure under ADR-014 Principle 3.
    - **P4 zero preservation** -- zero weight gives zero allocation.
      The shortfall ``r`` equals the sum of ``n`` fractional remainders
      each below 1, so ``r`` never exceeds the count of strictly positive
      remainders and is exhausted before any zero-weight key is reached.
    - **P5 order preservation** -- a key with weight at least another's
      receives at least as much.
    """
    if total < 0:
        msg = f"total must be non-negative, got {total}"
        raise ValueError(msg)
    if not weights:
        return {}

    for key, weight in weights.items():
        if not math.isfinite(weight):
            msg = f"weight for {key!r} is not finite: {weight!r}"
            raise ValueError(msg)
        if weight < 0:
            msg = f"weight for {key!r} is negative: {weight!r}"
            raise ValueError(msg)

    mass = math.fsum(weights.values())
    if mass <= 0:
        if total == 0:
            return dict.fromkeys(weights, 0)
        msg = (
            f"all weights are zero but total is {total}; the weight "
            f"cascade should have fallen back to uniform before here"
        )
        raise ValueError(msg)

    if total == 0:
        return dict.fromkeys(weights, 0)

    ideal = {k: total * w / mass for k, w in weights.items()}
    allocated = {k: int(math.floor(q)) for k, q in ideal.items()}
    shortfall = total - sum(allocated.values())

    if shortfall:
        # Largest fractional remainder first; key ascending breaks ties, so
        # the result does not depend on dict ordering.
        ranked = sorted(
            ideal, key=lambda k: (-(ideal[k] - allocated[k]), k)
        )
        for key in ranked[:shortfall]:
            allocated[key] += 1

    return allocated
