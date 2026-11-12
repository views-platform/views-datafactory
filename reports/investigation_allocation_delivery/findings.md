# How much allocated fatality mass is delivered to the wrong cell

**Date:** 2026-11-12
**Issue:** #548 · **Epic:** #547
**Method:** `scripts/measure_allocation_delivery.py` against
`data/viewpoint/kgi_kti_activity.parquet`, built 2026-11-12 (3:33 wall, peak RSS
**8,594,192 KB = 8.19 GiB** — within 0.01% of the independent 2026-11-06 measurement of
8,593,264 KB)
**Store:** local `data/consolidated/ucdp_store.parquet`, UCDP GED v25.1, stale-version
filter applied by the builder (`filter_stale_versions=True`)

---

## The number to quote

> **1,128,236 deaths across 60,105 events are delivered to a different grid cell than the
> one the allocator assigned them. That is 26.49% of all UCDP fatality mass in the
> viewpoint.**

This supersedes the indicative **32.8%** quoted when the epic was opened. The two are not
in conflict — they measure different things on different denominators, and both are stated
below so nobody re-derives the discarded one.

| | events | deaths | share |
|---|---:|---:|---:|
| Total in the viewpoint | — | 4,258,880 | 100% |
| **Eligible** — `where_prec >= 4`, the class the allocator may move | 62,818 | 1,319,567 | 30.98% |
| **Displaced** — delivered cell ≠ allocated cell | **60,105** | **1,128,236** | **26.49%** |

Displaced is **85.5% of eligible**. The remaining 14.5% is mass whose allocation happened to
land back on its own source cell — eligible and allocated, but not displaced. Keeping these
apart matters: *eligible* overstates the defect by about a sixth.

### Why the indicative figure was 32.8%

It was computed on the **consolidated store** (4,507,491 deaths) with **last-version-wins**
rather than the real stale-version filter, and it reported *eligible* rather than
*displaced*. Both corrections pull in the same direction. The measured figure is the one to
use.

---

## By spatial precision

| `where_prec` | meaning | rows | mass | displaced | displaced % |
|---:|---|---:|---:|---:|---:|
| 1 | exact | 196,516 | 1,540,422 | 37 | 0.00% |
| 2 | ≤ 25 km | 100,418 | 1,015,358 | 1 | 0.00% |
| 3 | admin-2 | 59,693 | 383,533 | 3 | 0.00% |
| **4** | **admin-1** | 578,842 | 383,810 | **294,319** | **76.68%** |
| **5** | **larger than admin-1** | 737,121 | 531,311 | **440,919** | **82.99%** |
| **6** | **country** | 965,730 | 401,816 | **390,963** | **97.30%** |
| 7 | international | 15,791 | 2,630 | 1,994 | 75.82% |

The gradient is the mechanism in plain view: the coarser UCDP's own location, the further the
allocator moves the mass, and so the more of it the delivery layer throws away. At
`where_prec = 6` — country-only — **97.3%** of the mass is delivered somewhere other than
where it was placed.

The 41 displaced deaths at `where_prec` 1–3 are not allocation; they are the pre-existing
disagreement described below.

### By violence type (displaced only)

| | deaths | rows |
|---|---:|---:|
| State-based (`tv=1`) | 919,117 | 1,771,677 |
| Non-state (`tv=2`) | 128,239 | 120,311 |
| One-sided (`tv=3`) | 80,880 | 342,780 |

State-based carries **81.5%** of the displaced mass, which is the slice the primary
evaluation metric uses.

---

## C-366's figures are confirmed exactly, not corrected

The epic assumed C-366's numbers were derived as loosely as the 32.8% and would need
restating. They were not.

**`where_prec` 4 + 6 — the set the retired `production_parity` filter excluded — is 43,933
events carrying 785,626 deaths.** Measured here to the unit, against the register's existing
figures. C-366 needs no correction; #556 should record it as **verified**, which is a
stronger statement than it had before.

Note what the filter did and did not do: it dropped `where_prec` 4 and 6 and **kept 5**, the
class that produced the Tigray artifact. It was never a precision threshold.

---

## The pre-existing disagreement, and a refuted ADR claim

Before any allocation, does UCDP's own `priogrid_gid` agree with its own coordinates?

**Almost always.** 70 of 441,394 events disagree — **0.016%**, carrying 3,257 deaths
(0.072%). Measured directly on the consolidated store, no build required.

But **ADR-015:104 explains these disagreements as *"border cells, precision issues"*, and
that is wrong.** A border effect means the two cells are neighbours: a pgid offset of 1
(east–west) or 720 (north–south) on the 720-column grid.

| offset | events |
|---|---:|
| 1 (east–west neighbour) | **0** |
| 720 (north–south neighbour) | 5 |
| median offset | **1,460 cells** |
| maximum offset | 66,290 cells |

Sixty-two of the seventy are `where_prec = 6`, where UCDP's declared cell and its coordinates
are independently-chosen representatives of a whole country and sit far apart. This is not
precision noise; it is two different answers to "where is this country".

The practical consequence is small — 3,257 deaths — but it matters for #551's fallback
design: when the declared cell and the coordinates disagree, they can disagree by thousands
of cells, so "either is about right" is not available as a justification. It also matters for
#556: the ADR amendment should correct the stated cause, not just record that the preference
is now implemented.

---

## Per-event footprint

Both summary events are `where_prec = 5` and both allocate across all **18** cells of their
admin-1 polygon. Both are delivered into **one**.

| | event 463131 | event 463137 |
|---|---:|---:|
| sum `best` | 113,368 | 121,848 |
| months | 12 (Jan–Dec 2021) | 3 (Aug–Oct 2022) |
| rows in the viewpoint | 216 (18 × 12) | 54 (18 × 3) |
| **allocated** cells | **18** | **18** |
| **delivered** cells | **1** | **1** |
| worst **allocated** cell-month | 11,732 · cell 150197 · 2021-06 | 29,620 · cell 150197 · 2022-08 |
| worst **delivered** cell-month | **31,937** · cell 148759 · 2021-06 | **80,633** · cell 148759 · 2022-08 |

The delivered figure for 463131 — 31,937 — is consistent with the **32,390** measured
independently from the served store on 2026-11-12; the difference is the server's fresher
harvest plus roughly 2,289 deaths of genuinely local events in that same cell.

---

## A target I pre-registered is unachievable, and must change before #557 runs

This is the most important thing in this document.

The falsifier set drafted for #553 and #557 contains:

> event 463131: worst delivered cell-month — target **< 5,000**

**Correct allocation cannot reach that, and I should have known.** The worst *allocated*
cell-month for 463131 is **11,732**. For 463137 it is **29,620**. Those are what the
allocator produces when it works perfectly; delivery cannot go below them.

ADR-053's own amendment already records the mechanism: activity weighting moves mass toward
months with observed fighting, so *"the event's own peak cell-month rises (3,471 uniform →
11,732 activity)"*. I wrote that sentence, then carried a `< 5,000` target into the new
falsifier set anyway. Pre-registering a target that the correct behaviour fails is worse than
having no target: it manufactures a failure and invites the bound to be widened afterwards,
which is exactly what pre-registration exists to prevent.

**The honest replacement**, for #553 and #557:

| what | target | why |
|---|---|---|
| event 463131: delivered cells | **= 18**, matching allocated | Delivery reproduces the allocation. The actual claim. |
| event 463131: worst delivered cell-month | **= worst allocated (11,732 ± fresh-data drift)** | Equality, not a bound. |
| event 463137: delivered cells | **= 18** | |
| event 463137: worst delivered cell-month | **= worst allocated (29,620 ± drift)** | |
| displaced mass | **0** | The one unambiguous target. |

And a statement that must travel with them: **activity weighting does not bound a cell-month
below any particular value.** It removes an artifact of measurement and replaces it with a
concentration that reflects observed fighting. Whether 29,620 state-based deaths in one
0.5° cell in August 2022 is *correct* is ADR-049's claim, and this epic does not test it.

---

## What this does not establish

- **That the delivered values will be right after #551** — only that the allocator's decision
  will survive. Whether proportional-to-well-located-fatalities is the correct allocation
  remains ADR-049's claim, and its held-out measurement was computed on allocated cells.
- **That 26.49% is the figure for the served store.** It is the figure for a 2026-11-12 local
  build. Production harvests fresher data; expect drift of a percent or so.
- **Anything about ACLED, V-Dem, SHDI, GHS-POP or GHS-BUILT-S.** ACLED does not allocate; the
  other four are pregridded and read their decided cell. Unaffected, and measured as such in
  the epic's survey.

## Reproducing this

```bash
uv run python scripts/build_viewpoint.py --profile kgi_kti_activity
uv run python scripts/measure_allocation_delivery.py
```

The baseline disagreement measurement is in this document's §"pre-existing disagreement" and
reads the consolidated store directly; it needs no build.

---

# Addendum, 2026-11-12: is it a spatial distortion at constant totals?

Prompted by a question from the views-postprocessing session, whose historical delivery leg
ships UCDP actuals at cell-month resolution to the FAO and to CRAF'd, placed by
`priogrid_id`. For that consumer the spatial placement is not an input it transforms — it is
the product. The question was whether displacement moves totals or only cells.

**It only moves cells. That is the worse answer.**

| of the 1,128,236 displaced deaths | mass | share |
|---|---:|---:|
| stays inside the same GAUL **country** | 1,127,001 | **99.89%** |
| stays inside the same **admin-1** | 749,531 | 66.43% |
| crosses a country border | 1,235 | 0.11% |

By precision code, the share of displaced mass staying in the same polygon:

| `where_prec` | displaced | same country | same admin-1 |
|---:|---:|---:|---:|
| 4 | 294,319 | **100.00%** | **100.00%** |
| 5 | 440,919 | **100.00%** | **100.00%** |
| 6 | 390,963 | 99.68% | **3.43%** |
| 7 | 1,994 | 100.00% | 41.62% |

Codes 4 and 5 are allocated *within* the polygon the nominal coordinate already sits in, so
every aggregate above cell level reconciles exactly. Code 6 preserves the country and destroys
the admin-1 distribution, which is expected: a country-level event is spread nationwide and
then collapsed to a single point.

**Country-month sums reconcile. Admin-1 sums reconcile for codes 4 and 5. Cell-level is
wrong, and every check that aggregates passes.** A consumer validating totals, coverage or
country reconciliation sees nothing.

## The concentration

| `where_prec` | allocated cells | delivered cells |
|---:|---:|---:|
| 4 | 6,289 | **943** |
| 5 | 5,343 | **1,896** |
| 6 | 6,896 | **91** |

390,963 deaths of country-level events are delivered into **91 cells** — about 4,300 deaths
per cell, wherever UCDP's nominal country point falls.

## Correction: how long this has been delivered, which is shorter than first stated

The epic states the spatial allocation has never affected delivered data. That is true of the
**allocator**, and it is the right statement about the mechanism. It is **not** the right
statement about the delivered consequence, and the difference matters to anyone asking "for
how many releases".

Before v1.18.0 production ran `production_parity`, which sets
`spatial_distribution_strategy="passthrough"` **and** `exclude_where_prec=(4, 6)`:

- **`where_prec` 4 and 6 — 685,282 of the displaced mass — were absent from delivered data,
  not misplaced within it.** They were dropped.
- **`where_prec` 5 — 440,919 — sat at its nominal centroid in every prior release.** Under
  `passthrough` that is the declared behaviour, not a defect. Its delivered placement is
  unchanged by v1.18.0, which is why cell 148759 held 113,395 before and 115,657 now.

So the **2026-11-11 run** is the first to deliver codes 4 and 6 at all, and it delivered them
immediately misplaced — 685,282 deaths concentrated into roughly 1,034 cells.

**One release, not many.** A delivery staged before 2026-11-11 does not carry the new mass.

This correction was produced by a consumer asking (3) separately from (1), and it would not
have surfaced otherwise: "the allocator never worked" and "the delivered data has always been
wrong in this way" are different claims, and only the first one was measured.
