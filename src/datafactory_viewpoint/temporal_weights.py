"""Monthly activity indicators for temporal allocation.

The temporal counterpart of :mod:`datafactory_viewpoint.spatial_weights`.
Where that module answers "within this polygon, which cells see fighting",
this one answers "within this span, which months see fighting" -- so that
an event UCDP declares temporally imprecise can be placed by observed
activity rather than spread flat.

**Measured, before this was built** (see
``scripts/evaluate_temporal_allocation.py``, 20,000 coarsened events whose
true month is known): activity weighting cuts the mean distance from the
true month from 4.883 months to 3.305 (-32.3%) and raises the share of
mass landing in the right month from 0.0825 to 0.1525 (+84.8%), beating
uniform on 64.9% of events against 22.9% worse. Option T2 in
``reports/2026-11-04_summary_event_allocation_dossier/11_allocator_spec.md``
only existed as a hypothesis until that measurement; the same script is
what would falsify it.

**The indicator pool is deliberately strict.** Activity is counted only
from events that are well located *and* well dated (``where_prec <= 2``
and ``date_prec <= 2``). ``where_prec == 3`` is an admin-2 **centroid**
assignment -- precisely coded rather than precisely known -- and using it
would build the indicator partly out of the artefact the allocator exists
to undo.

**The cascade exists because no single actor key covers everything.**
Dyad is the most specific and carries 98.6% of cases; conflict, then
``side_b``, then country widen the net; uniform is the floor. Every level
is tried in order and the first with nonzero activity across the span
wins.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pyarrow as pa
import pyarrow.compute as pc

__all__ = [
    "TemporalWeightMap",
    "build_temporal_weight_map",
    "CASCADE_KEYS",
]

logger = logging.getLogger(__name__)

#: VIEWS month_id epoch: ``month_id = (year - 1980) * 12 + month``.
_EPOCH_YEAR = 1980

#: Only events this precise contribute to the indicator. See the module
#: docstring on why 3 is excluded.
_POOL_WHERE_PREC = 2
_POOL_DATE_PREC = 2

#: Cascade order, most specific first. The event's value for each key is
#: read off the event dict under the same name.
CASCADE_KEYS: tuple[str, ...] = (
    "dyad_new_id",
    "conflict_new_id",
    "side_b_new_id",
    "country_id",
)


@dataclass(frozen=True)
class TemporalWeightMap:
    """Monthly fatality activity, keyed by actor identifier and month.

    Attributes:
        activity: cascade key name -> {(key value, month_id): fatalities}.
            One sub-dict per entry in :data:`CASCADE_KEYS`. Absent pairs
            mean no well-observed activity, which allocation treats as
            zero weight -- and zero weight means zero allocation, by the
            apportionment rounder's zero-preservation property.
        n_pool_events: how many events contributed, for provenance.
    """

    activity: dict[str, dict[tuple[int, int], float]]
    n_pool_events: int

    def lookup(self, key: str, key_value: int, month_id: int) -> float:
        """Activity for one (key, value, month), or 0.0 if unobserved."""
        return self.activity.get(key, {}).get((key_value, month_id), 0.0)


def build_temporal_weight_map(table: pa.Table) -> TemporalWeightMap:
    """Build monthly activity indicators from the consolidated table.

    Args:
        table: Consolidated event table, after stale-version filtering so
            that the indicator reflects the same events the viewpoint
            will emit.

    Returns:
        A :class:`TemporalWeightMap` over :data:`CASCADE_KEYS`.

    Raises:
        KeyError: if a required column is absent -- fail loud rather than
            silently produce an empty indicator that would make every
            allocation fall through to uniform (ADR-011).
    """
    required = {
        "best", "date_start", "date_prec", "where_prec", *CASCADE_KEYS,
    }
    missing = required - set(table.column_names)
    if missing:
        msg = (
            f"consolidated table lacks columns needed for temporal "
            f"activity: {sorted(missing)}"
        )
        raise KeyError(msg)

    pool = table.filter(
        pc.and_(
            pc.less_equal(table["where_prec"], _POOL_WHERE_PREC),
            pc.less_equal(table["date_prec"], _POOL_DATE_PREC),
        )
    )

    best = pool["best"].to_pylist()
    starts = pool["date_start"].to_pylist()
    key_values = {k: pool[k].to_pylist() for k in CASCADE_KEYS}

    activity: dict[str, dict[tuple[int, int], float]] = {
        k: {} for k in CASCADE_KEYS
    }
    n_used = 0
    for i, raw_start in enumerate(starts):
        value = best[i]
        if not value or value <= 0 or not raw_start:
            continue
        text = str(raw_start)
        if len(text) < 7:
            continue
        try:
            year, month = int(text[:4]), int(text[5:7])
        except ValueError:
            continue
        month_id = (year - _EPOCH_YEAR) * 12 + month
        n_used += 1
        for key in CASCADE_KEYS:
            key_value = key_values[key][i]
            if key_value is None:
                continue
            bucket = activity[key]
            pair = (int(key_value), month_id)
            bucket[pair] = bucket.get(pair, 0.0) + float(value)

    logger.info(
        "Temporal activity map: %d pool events (where_prec<=%d, "
        "date_prec<=%d) over %s",
        n_used,
        _POOL_WHERE_PREC,
        _POOL_DATE_PREC,
        ", ".join(f"{k}={len(activity[k])} pairs" for k in CASCADE_KEYS),
    )
    return TemporalWeightMap(activity=activity, n_pool_events=n_used)
