# Class Intent Contract: TemporalWeightMap

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-11-12
**Related ADRs:** ADR-003, ADR-011, ADR-014, ADR-053

---

## 1. Purpose

> The precomputed answer to "within this span, which months see fighting?" — observed
> monthly fatality activity keyed by actor identifier, so that an event UCDP declares
> temporally imprecise can be placed by what was observed rather than spread flat.

Built by `build_temporal_weight_map` from the consolidated store and read by
`temporal_distribution.activity_weighted`. The exact counterpart of `SpatialWeightMap`:
that one indexes space, this one indexes time, and the two are consumed by sibling
strategies on independent axes.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** allocate. It answers lookups; `activity_weighted` decides which
  key to use and `apportionment.apportion` does the integer arithmetic.
- This class does **not** choose the cascade level. It stores one sub-map per key and lets
  the consumer walk them in order.
- This class does **not** know the span of any event, or what triggers allocation. The
  `date_prec >= 4` plus multi-month-span trigger is the strategy's.
- This class does **not** interpret a missing entry. It returns `0.0`; what zero *means* is
  the consumer's decision, and it is a consequential one (§4).
- This class does **not** persist itself, and does **not** touch space. Cells, polygons and
  crosswalks are all outside its world.

---

## 3. Responsibilities and Guarantees

- Immutable: frozen dataclass, two fields and one method.
- `activity` has exactly one sub-dictionary per entry in `CASCADE_KEYS` — dyad, conflict,
  `side_b`, country — always all four, even when a key contributed nothing. The sub-dict is
  then empty rather than absent.
- Each sub-dictionary is keyed by `(key value, month_id)` and holds summed `best` fatalities.
  `month_id` follows the VIEWS epoch, `(year - 1980) * 12 + month`.
- `lookup` returns `0.0` for any unobserved triple and never raises. It is the only method,
  and it is total.
- `n_pool_events` is the number of events that contributed — not the number of rows scanned,
  and not the number of `(key, month)` pairs. It exists for provenance: a map built from a
  pool far smaller than expected is the signature of a wrong precision filter or a
  truncated store.
- **The pool is deliberately strict**: an event contributes only when it is both well
  located *and* well dated, `where_prec <= 2` **and** `date_prec <= 2`. `where_prec == 3` is
  an admin-2 *centroid* assignment — precisely coded rather than precisely known — and
  admitting it would build the indicator partly out of the artefact the spatial allocator
  exists to undo. This is tighter than `SpatialWeightMap`'s `where_prec <= 3` pool, and the
  asymmetry is intentional.
- Events with null, zero or negative `best`, or an unparseable `date_start`, are skipped and
  do not count toward `n_pool_events`.

### The cascade this class participates in, stated in full

1. For each key in `CASCADE_KEYS`, most specific first, the consumer reads the event's own
   value for that key. A null value skips the level.
2. It looks up every month of the span under that key and takes the level as chosen if the
   activity sums to **more than zero anywhere in the span**. Dyad carries 98.6% of cases.
3. No level with any activity, or no weight map at all → fall back to `uniform_span`. Never
   to flat-on-the-end-month, which is the behaviour being replaced.

**The chosen level is recorded in the output**, on `_temporal_weight_key`. Rows allocated by
the uniform fallback carry `_temporal_distributed` and `_temporal_n_months` but no
`_temporal_weight_key`, so the two branches are distinguishable in the delivered data by
a reader who knows to look. Its spatial sibling does not yet have this property, and this is
the shape that one should take.

---

## 4. Inputs and Assumptions

`build_temporal_weight_map` takes the consolidated event table and nothing else.

- The table is assumed **already stale-version filtered**, so that the indicator reflects
  the same events the viewpoint will emit.
- Required columns: `best`, `date_start`, `date_prec`, `where_prec`, and all four cascade
  keys. All are checked up front, together, and a missing one raises (§6).
- `date_start` is assumed to be an ISO-8601 date string. Only the first seven characters are
  read; anything shorter is skipped silently as unparseable.
- The month axis is assumed to be the VIEWS epoch. The epoch constant is local to
  `temporal_weights` and is one of several independent re-derivations of `month_id` in the
  repository; they agree today, and that agreement is not asserted anywhere.

**The assumption most likely to be wrong, stated because it is consequential:** a month with
no entry gets `0.0`, and zero weight means zero allocation by the apportionment rounder's
zero-preservation property. That says "no well-observed fighting here, so do not invent
any", which is what separates activity weighting from smearing. But absence of well-located
reporting is not absence of fighting — 1,760 KTI events have at least one zero-activity month
inside their span. The behaviour is deliberate, measured, and still an assumption.

---

## 5. Outputs and Side Effects

A `TemporalWeightMap`. No I/O, no mutation of its input, no state outside the returned
object.

`build_temporal_weight_map` logs one informational line: the pool size, both precision
thresholds, and the number of `(value, month)` pairs per cascade key. Read it on every
build — the per-key pair counts are the cheapest check that the cascade has anything to
cascade over.

---

## 6. Failure Modes and Loudness

**Loud, by construction and better than its spatial sibling:**

- Required columns are checked as a **set, before any work**, and a missing one raises
  `KeyError` naming every absent column. The docstring states the reason explicitly: an
  empty indicator would make every allocation fall through to uniform, which conserves and
  therefore looks correct (ADR-011). Failing early is the point.

**Silent, and stated here as true rather than as a guarantee:**

- A `date_start` shorter than seven characters, or one whose year or month will not parse,
  is skipped without a warning. Such a row is simply absent from `n_pool_events`, so a
  systematically malformed date column shows up only as a pool smaller than expected.
- A table whose events are all imprecise builds successfully and returns four empty
  sub-maps. Every allocation then takes the uniform fallback. Nothing raises; the logged
  pair counts are the only signal.

`lookup` is total by design and must not be made to raise. A caller that needs to tell
"zero observed" from "key absent" must inspect `activity` directly.

---

## 7. Boundaries and Interactions

- Lives in the viewpoint layer and reads the consolidated store as opaque parquet.
- It must **not** import from `datafactory_compilation` or `datafactory_harvester`, and must
  not reach into `spatial_weights`. The two axes are independent and their only shared
  machinery is `apportionment`.
- Its only consumer is `temporal_distribution.activity_weighted`. Nothing downstream of the
  viewpoint sees this object; what crosses that boundary is the allocated rows and the
  `date_month` on them.
- It owns `CASCADE_KEYS`, which the consumer imports rather than re-declares — the order is
  part of the contract, not a convention duplicated at the call site.

---

## 8. Examples of Correct Usage

```python
weight_map = build_temporal_weight_map(consolidated_after_stale_filter)
rows = activity_weighted(event, weight_map)
```

```python
# Walking the cascade the way the strategy does, most specific first.
for key in CASCADE_KEYS:
    value = event.get(key)
    if value is None:
        continue
    span = [weight_map.lookup(key, int(value), m) for m in month_ids]
    if sum(span) > 0:
        break
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: built from the unfiltered store. A month carrying an event in three
# source versions gets three times its true activity, and nothing says so.
weight_map = build_temporal_weight_map(raw_consolidated)
```

```python
# WRONG: reads one key only. Dyad covers 98.6% of cases, which means it
# misses one in seventy -- and those fall through to uniform silently
# because the caller never tried the wider keys.
w = weight_map.lookup("dyad_new_id", dyad, month_id)
```

```python
# WRONG: treats a zero lookup as "no data" and substitutes a uniform weight
# for that month alone. Zero means "no well-observed fighting", and mixing
# the two weightings within one span conserves while allocating by neither.
```

---

## 10. Test Alignment

- **Green:** `tests/test_activity_weighted.py::TestActivityDrivesTheAllocation` asserts that
  activity concentrated in one month lands there, that two active months split by their
  weights, and that a zero-activity month receives nothing.
  `TestTheCascade` walks all four levels, asserting dyad is preferred and that each absent
  level falls through to the next.
- **Red:** `TestFallbacks` asserts the three ways this class can fail to inform an
  allocation — no weight map, no activity at any level, and the one that matters most,
  `test_fallback_is_uniform_not_endpoint`: the fallback must be `uniform_span`, not
  flat-on-the-end-month. That is an assertion about a branch not taken, and the wrong
  behaviour would conserve and otherwise pass.
- **Beige:** `TestConservationAndTrigger` covers precise dates and single-month spans, both
  of which must not be allocated at all.
- `tests/test_synthetic_spatial_fixtures.py::TestSyntheticUcdpEventsGreen` asserts the pool
  is **not empty** on the synthetic fixtures, with the reason stated in the test: otherwise
  every temporal allocation falls through to uniform and the suite would prove nothing.
- Conservation is the invariant that must not regress: `best`, `low` and `high` are each
  conserved exactly across the span, asserted by
  `test_conserves_every_extensive_field`.

**A gap, found while writing this contract rather than asserted by it:** nothing tests the
pool threshold itself. No test plants a `where_prec == 3` event and asserts it is excluded,
so the §3 claim that the pool is stricter than its spatial sibling's rests on reading the
constant, not on a guard. Raising the threshold to 3 would change every allocation and no
test would go red.
- The guarantee this class's evidence base got wrong once, and which tests must now state at
  the layer it is measured: a figure grouped by the allocator's own output is not a
  delivered figure. `scripts/evaluate_temporal_allocation.py` measures the allocation, not
  the delivery, and says so in its own warning block.

---

## 11. Evolution Notes

**Stable:** the two fields, the total `lookup`, the four-key cascade and its order, and the
`where_prec <= 2` / `date_prec <= 2` pool.

**Expected to change:** nothing in the class's shape. The open question is §4's zero
assumption, which is a research question about under-reporting, not a contract defect.

**Would require revisiting this contract:** adding or reordering a cascade key; making the
pool thresholds configurable; weighting by anything other than fatality mass; or treating an
unobserved month as a small positive weight, which would change what zero means and so
change the meaning of every allocation.

---

## End of Contract

This document defines the **intended meaning** of `TemporalWeightMap`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
