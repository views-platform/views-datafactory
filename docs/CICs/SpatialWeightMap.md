# Class Intent Contract: SpatialWeightMap

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-11-12
**Related ADRs:** ADR-003, ADR-011, ADR-014, ADR-039, ADR-049

---

## 1. Purpose

> The precomputed answer to "within this polygon, which cells see fighting?" — per-cell
> shares of well-located fatality mass inside each GAUL admin-1 and country polygon, built
> once per viewpoint build and read by the spatial distribution strategies.

UCDP codes many events to a polygon rather than a point. `spatial_distribution.proportional`
turns such an event into one row per cell, and this class is where it gets the proportions:
the share of the polygon's *well-located* deaths that each of its cells accounts for. Built
by `build_spatial_weight_map`. Its temporal counterpart is `TemporalWeightMap`.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** allocate anything. It holds shares; `spatial_distribution`
  applies them, and `apportionment.apportion` does the integer arithmetic.
- This class does **not** decide which polygon level an event belongs to. The
  admin-1-or-country choice is the consumer's, made from `where_prec`.
- This class does **not** validate GAUL geometry, adjacency or coverage. It trusts the
  crosswalk parquets as produced by the area-majority generator (ADR-039).
- This class does **not** persist itself. It is rebuilt from the consolidated store on every
  viewpoint build, which is what makes a viewpoint disposable (ADR-014).
- This class does **not** know anything about compilation, the grid array, or months.

---

## 3. Responsibilities and Guarantees

- Immutable: frozen dataclass, six mapping fields, no methods.
- Within every polygon present in `admin1_weights` or `country_weights`, the shares sum to
  1.0 and each share is strictly positive.
- A polygon appears in `admin1_weights` / `country_weights` **only if** its well-located
  fatality total is strictly positive. A polygon with no well-located deaths is absent, not
  present-with-zeros. This absence is the trigger for the uniform fallback described below.
- `pgid_to_gaul1` / `pgid_to_gaul0` map **every** cell the crosswalk assigns to a polygon.
  Cells whose crosswalk value is `-1` — water and unassigned — are absent from both, and an
  event whose centroid lands on one is passed through unallocated.
- `admin1_all_cells` / `country_all_cells` list **every** cell of each polygon, ascending,
  independent of whether any fatalities were observed there. They are the exact inverse of
  the two `pgid_to_*` maps.
- "Well located" means `where_prec <= 3`. The threshold lives in `spatial_weights` as a
  module constant, and it is deliberately *looser* than `TemporalWeightMap`'s pool.

### The precedence this class participates in, stated in full

The fields encode a two-stage decision that is decision-relevant and belongs here rather
than only in a docstring. For an event the consumer has decided to distribute:

1. Polygon level from `where_prec` — country for `>= 6`, admin-1 for 4 and 5.
2. The polygon's code from `pgid_to_gaul0` / `pgid_to_gaul1`, keyed on the event's own
   centroid cell. **No code → the event is passed through unchanged**, with a warning.
3. That polygon's entry in `country_weights` / `admin1_weights`. Present and non-empty →
   allocate proportionally to observed fatalities.
4. **Absent or empty → allocate uniformly**, `1 / len(all_cells)` over every cell of the
   polygon, from `country_all_cells` / `admin1_all_cells`.
5. No cells either → pass through unchanged.

Step 4 is why the `*_all_cells` fields exist, and it is the branch most likely to be
misread: an event allocated uniformly is spread across the whole polygon and conserves its
totals exactly, so **it looks indistinguishable from a proportional allocation in every
aggregate**. Anyone measuring whether proportional allocation works must plant unequal
fatalities in their fixture; equal weights cannot tell step 3 from step 4.

**This is not currently observable in the output.** Allocated rows carry
`_spatial_distributed`, `_spatial_source_pgid`, `_spatial_polygon_code` and
`_spatial_n_cells`, and none of them records *which* of the two weightings was used. Step 4
also emits no log line, while steps 2 and 5 both warn. Within this contract's scope that is
a stated gap, not a guarantee — see §6.

---

## 4. Inputs and Assumptions

`build_spatial_weight_map` takes the consolidated event table and two crosswalk paths.

- The table is assumed to be **already stale-version filtered**, so the indicator is built
  from the same events the viewpoint will emit. Passing an unfiltered table silently
  over-weights cells that appear in several source versions.
- The table must carry `where_prec`, `priogrid_gid` and `best`. A row whose `priogrid_gid`
  is null contributes nothing; a null `best` counts as zero.
- Each crosswalk parquet must carry `gid` and `value` columns. `value == -1` and null both
  mean unassigned and are dropped.
- The crosswalk is assumed to be complete over the PRIO-GRID — 259,200 rows — and
  area-majority rather than centroid-derived (ADR-039).

Shares are `float`, computed in double precision. They are proportions, not counts: the
rounding to whole deaths happens later, in the apportionment step, which conserves the
event's total exactly.

---

## 5. Outputs and Side Effects

A `SpatialWeightMap`. No I/O, no mutation of its inputs, no state outside the returned
object.

`build_spatial_weight_map` logs two informational lines: the size of each crosswalk, and the
number of polygons with weights alongside the number of well-located events and distinct
cells they came from. Those counts are the only visibility into how much of the map is real
and should be read on every build — a map covering far fewer polygons than expected is the
signature of a wrong or truncated crosswalk.

---

## 6. Failure Modes and Loudness

**Loud, by construction:**

- A missing crosswalk parquet raises `FileNotFoundError` with the path, logged at error
  level, before anything else happens.
- A crosswalk missing `gid` or `value` raises from the parquet reader.
- A consolidated table missing `where_prec`, `priogrid_gid` or `best` raises from the filter
  or column access.
- Mismatched column lengths raise, because the zips are strict.

**Silent, and stated here because it is the honest reading of the code:**

- A table containing **no** well-located events builds successfully and returns a map with
  empty `admin1_weights` and `country_weights`. Every subsequent allocation then takes the
  uniform fallback. Nothing raises and nothing warns; the only signal is the logged count of
  polygons with weights being zero.
- The uniform fallback itself (§3, step 4) is not logged, not counted, and not recorded on
  the rows it produces. A build in which every allocation was uniform is not distinguishable
  from one in which every allocation was proportional, except by re-deriving the weights.

Both are gaps against ADR-003's rule that a decision-relevant fallback must not be silent.
They are recorded in the risk register rather than fixed inside this contract; a CIC states
what is true, and these are true.

---

## 7. Boundaries and Interactions

- Lives in the viewpoint layer. It may read GAUL crosswalk artefacts and the consolidated
  store, both as opaque parquet.
- It must **not** import from `datafactory_compilation` or `datafactory_harvester`. The
  grid, the month axis and the harvesters are all outside its world.
- Its only consumers are the spatial distribution strategies and the tests that exercise
  them. Nothing downstream of the viewpoint sees this object; what crosses that boundary is
  the allocated rows.
- It trusts `cell_generator`'s PRIO-GRID identity convention — cells are 1-indexed — without
  re-deriving it.

---

## 8. Examples of Correct Usage

```python
weight_map = build_spatial_weight_map(
    table=consolidated_after_stale_filter,
    gaul1_path=admin_dir / "gaul1_code.parquet",
    gaul0_path=admin_dir / "gaul0_code.parquet",
)
rows = proportional(event, weight_map)
```

```python
# Reading the two branches apart, which the output does not record for you:
code = weight_map.pgid_to_gaul1[event["priogrid_gid"]]
was_proportional = bool(weight_map.admin1_weights.get(code))
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: built from the unfiltered store. Cells carrying an event in three
# source versions get three times their true share, and nothing says so.
weight_map = build_spatial_weight_map(raw_consolidated, g1, g0)
```

```python
# WRONG: treats absence as zero fatalities in a real polygon. Absence from
# admin1_weights means "no well-located deaths observed", which is exactly
# when the consumer must fall back to uniform over admin1_all_cells.
share = weight_map.admin1_weights.get(code, {}).get(pgid, 0.0)
```

```python
# WRONG: a fixture with equal fatalities per cell. Proportional and uniform
# produce identical output, so the test passes under either and proves neither.
```

---

## 10. Test Alignment

- **Green:** `tests/test_spatial_distribution.py::TestWeightMapGreen` asserts the four
  guarantees of §3 directly — shares sum to one, only well-located events contribute, cells
  with a `-1` crosswalk value are excluded, and `*_all_cells` is populated for every
  polygon. `TestProportionalGreen` then asserts the level choice at each `where_prec` from 4
  to 7, conservation on all three fields, and the provenance annotations.
- **Red:** the synthetic fixtures carry **deliberately unequal** per-cell fatalities —
  180/100/200/300/150/120 across polygon A's weighted cells, with **two of its eight cells
  carrying none** — so a proportional allocation and the uniform fallback produce different
  cell sets and different values. Equal weights would make the suite blind to §3 step 4.
  `tests/test_synthetic_spatial_fixtures.py` asserts the fixture's own cell round-trip, so
  the fixture cannot disagree with the grid code it is testing against.
- **Beige:** `TestProportionalBeige` covers the branches that conserve while doing something
  different — `test_zero_fatality_polygon_uniform` pins step 4, a single-cell polygon,
  `where_prec == 3` at the trigger boundary, and a centroid in water passing through.

**The proportionality guarantee, and where it is actually guarded.** The substance of §3
step 3 — that shares are proportional to *observed fatalities* rather than flat — breaks at
two independent seams, and they were not equally covered. An independent mutation audit
attacked the first; moving the same mutation to the second found the real gap.

- **Seam one, the shares themselves.** Replacing `_compute_weights`'s `deaths / total` with a
  flat `1.0 / n` is caught by `tests/test_spatial_distribution.py::TestWeightMapBeige::test_multiple_events_same_cell`,
  which asserts 0.6 and 0.4 on a two-cell polygon and has done since the original ADR-049
  implementation. Proportionality here has always been guarded in CI — incidentally, by a test
  whose stated subject is event aggregation. `TestWeightMapGreen::test_each_weight_is_its_cell_share_of_polygon_deaths`
  now asserts it directly, at both polygon levels, over four cells whose shares are pairwise
  distinct and none of which equals `1/n` of either polygon.
- **Seam two, whether the allocator uses them.** Equalising the weights inside `proportional`
  — same cell set, equal magnitudes — was caught by **nothing that runs in CI**. Every test in
  `TestProportionalGreen` asserted the total and the cell set, and both are invariant to the
  weights: 100 deaths over 50/30/20 arrives as 34/33/33, three cells, total 100, and all of
  them passed. The only test in the suite that caught it was
  `tests/test_adr049_profile_contract.py::TestAdr049GoldenCriterion::test_allocation_is_proportional_to_the_weight_map`,
  which is `skipif`'d on the real store and the GAUL crosswalks that CI never has — correct,
  and never runs, which is the mechanism that hid the defect this epic exists to fix.
  `TestProportionalGreen::test_each_cell_receives_its_weighted_share_not_an_equal_one` now
  asserts the per-cell magnitudes of `best`, `low` and `high`.

The first bullet corrects an earlier reading of the audit recorded here on 2026-11-12, which
said the guarantee was unguarded in CI outright. It was not; the audit's scope was the guards
this epic added, and a pre-existing one covered seam one. The absence was real but one layer
lower, and only re-running the mutation at the second seam established that.

**What "proportional" is pinned to, quantitatively.** An independent re-audit of the two
guards above found that the first one initially pinned the *size* of a weighting error rather
than the property: quantising every share with `round(share, 2)` passed the entire suite,
because the fixture's shares were all exactly representable at two decimal places. That
matters beyond the test, because quantisation is how proportionality degrades in practice —
in a polygon with many cells the small ones round to zero weight and receive nothing, and a
polygon whose every cell rounds to zero makes `apportion` raise. The fixture now uses prime
fatality counts, and the measured boundary is that `round(share, 6)` is caught while
`round(share, 7)` survives. So the guarantee this section states is enforced to roughly one
part in a million, not merely "not flat".

Note that both are a different uniformity from §3 step 4: the fallback spreads over the
polygon's *whole* cell list and so changes the cell set, which many guards see; replacing the
weights changes only the magnitudes, which until now almost nothing did.
- The guarantee that must not regress is end-to-end rather than local: an allocation of N
  cells must be **delivered** as N cells through the real compiler. Asserted by
  `tests/test_falsification_spatial_allocation_delivery.py`, which runs without any real
  GAUL parquets so it cannot skip.

---

## 11. Evolution Notes

**Stable:** the six fields, the sum-to-one guarantee, the absent-not-zero rule, and the
`where_prec <= 3` pool.

**Expected to change:** the silence of the uniform fallback. Recording the weighting used on
each allocated row — or counting the fallbacks at build time — would close the §6 gap
without touching this class's shape, and is the change this contract most expects.

**Would require revisiting this contract:** making the pool threshold configurable;
weighting by anything other than fatality mass; or caching the map across builds, which
would break the disposability ADR-014 relies on.

---

## End of Contract

This document defines the **intended meaning** of `SpatialWeightMap`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
