# Pre-registration: what the fix must deliver

**Written 2026-11-12, before the verification run.** Issue #553 (part), epic #547.

Pre-registration recorded in its own file, dated, ahead of the run it grades — because the
previous release was graded against numbers that were revised in the telling. If a row below
fails, **that is a finding, not a threshold to move.**

---

## Why this file exists at all

The v1.18.0 release was verified against eight pre-registered numbers and passed. Then
reading the **served store** showed three of the four measurable targets failing.

Both halves of that went wrong:

1. **All eight numbers were computed by grouping on `priogrid_gid`** — the field the delivery
   layer ignores. `scripts/evaluate_temporal_allocation.py:70` and
   `scripts/investigate_summary_event_concentration.py` both do this, as did every figure in
   ADR-049, ADR-053 and the dossier. They described a quantity no consumer receives.
2. **One target passed for the wrong reason.** December 2021 was chosen because that is where
   the old defect dumped everything. After temporal spreading December holds a small share, so
   the cell read 1,782 — a 64× improvement. The worst cell-month across 2021 is **32,390**:
   3.5×. **Checking the single month the old defect concentrated in flattered the result by a
   factor of 18.**

The rule that follows, and the reason this file is dated:

> **A number is evidence only if it was measured where the consumer reads it.**

Every row below is therefore read from the **served store** through
`datafactory_query.load_dataset` — the consumer entry point, the same function a model's
dataloader calls — and not from a local parquet in this repository.

---

## The falsifier set

`today` is the served store as measured 2026-11-12, after the v1.18.0 run.
`expected` is computed from the allocated placement the fixed compiler now binds on,
measured on a 2026-11-12 local build.

| # | what | today | expected | criterion |
|---|---|---:|---:|---|
| 1 | event 463131: distinct delivered cells | 1 | 18 | **= 18**, equal to allocated |
| 2 | event 463137: distinct delivered cells | 1 | 18 | **= 18**, equal to allocated |
| 3 | delivered mass whose cell ≠ its allocated cell | 1,128,236 | 0 | **= 0** |
| 4 | cell 148759, 2021-12, state-based | 1,782 | 240 | **< 1,000** |
| 5 | month 504: largest state-based cell | 1,782 | 642 | **< 5,000** |
| 6 | month 504: largest cell's share of the slice | 37.67% | 13.61% | **< 25%** |
| 7 | month 504: slice ESS | 5.30 | 20.24 | **> 10** |
| 8 | month 504: cells with state-based mass | **223** | 283 | ~~> 100~~ **withdrawn — see below** |
| 9 | event 463131: worst delivered cell-month, whole span | 31,937 | 11,732 | **= worst allocated, ± drift** |
| 10 | event 463137: worst delivered cell-month, whole span | 80,633 | 29,620 | **= worst allocated, ± drift** |
| 11 | ACLED compiled output | — | unchanged | **byte-identical** to pre-fix |
| 12 | `.zattrs` `source_digest` | `6f049a5e1f5f5317` | moves | **≠ 6f049a5e1f5f5317** |

**Production harvests fresher data first, so every figure drifts by a percent or so.** Rows
4–8 are bounds wide enough to survive that. Rows 1, 2, 3, 11 and 12 are exact. Rows 9 and 10
are equalities against a quantity that itself moves with the data, hence "± drift" — if they
miss by more than a few percent, re-measure the allocated value before concluding anything.

---

## Row 8 is withdrawn, because it cannot fail

Criterion 8 was *"month 504 has more than 100 cells with state-based mass"*, written from the
expectation of 283. Reading the **current, broken** store gives **223**. The criterion is
already satisfied by the defect it was meant to detect, so it would have passed either way and
contributed nothing but false reassurance.

Withdrawn rather than tightened. The discriminating version of the same idea is already row 6
— the largest cell's share of the slice, 37.67% today against 13.61% expected — and a second
weaker proxy for it adds noise, not evidence.

**The lesson, which cost nothing here only because the measurement was run before the run:**
a pre-registered criterion must be checked against the *current, broken* state to confirm it
can fail. A criterion that passes on today's data is the pre-registration equivalent of a
vacuous assertion — mutation category M1, applied to a number instead of a test. Rows 1–7 and
9–12 were each confirmed to fail today; row 8 was the only one that was not, and it was the
only one that did not survive.

This is the third error found in this falsifier set by measuring rather than reasoning: the
unachievable `< 5,000` bound (below), the `priogrid_gid` grouping that produced the original
eight numbers, and now a criterion that cannot fail.

---

## Rows 9 and 10 are equalities, not bounds, and that is a correction

An earlier draft of this set targeted *"worst delivered cell-month **< 5,000**"* for row 9.
**Correct allocation cannot reach that.** The worst *allocated* cell-month is 11,732 for event
463131 and 29,620 for 463137 — that is what the allocator produces working perfectly, and
delivery cannot go below it.

ADR-053's amendment had already recorded the mechanism: activity weighting moves mass toward
months with observed fighting, so *"the event's own peak cell-month rises (3,471 uniform →
11,732 activity)"*. The `< 5,000` bound was carried into the falsifier set regardless.

Pre-registering a target that correct behaviour fails is worse than having no target: it
manufactures a failure, and then invites the bound to be widened afterwards — which is the one
thing pre-registration exists to prevent. Caught before the run, which is the only acceptable
time to catch it.

**The distinction that produced the error, stated so it is not repeated:** row 5 is *month
504's largest cell*, which is 642 and clears < 5,000. Row 9 is *event 463131's own worst
cell-month across its whole twelve-month span*, which is 11,732 and never clears it. Two
different quantities, both of which sound like "worst cell-month".

---

## What a pass does not establish

**That the delivered values are *right*.** Only that the allocator's decision survives to the
consumer. Whether proportional-to-well-located-fatalities is the correct way to place an
imprecisely-located event is ADR-049's claim, and ADR-049's own held-out measurement was
computed on allocated cells — one layer above delivery. This set tests delivery, not
allocation quality.

**That a cell-month is now small.** It is not. Activity weighting does not bound a cell-month
below any value; it removes an artifact of measurement and replaces it with a concentration
that reflects where fighting was recorded. Whether 29,620 state-based deaths in one 0.5° cell
in August 2022 is correct is a question this epic does not ask.

**That the seasonality question is closed.** December's share falls 12.27% → 6.62%, under
ADR-053's 9.0% guard — but August rises 6.66% → 11.30% and becomes the largest month. Measured,
recorded, and not an acceptance criterion here.

---

## How each row is read

```bash
# Rows 1-10: against the served store, through the consumer entry point
uv run python scripts/measure_allocation_delivery.py --source <served>

# Row 11: ACLED must be untouched by this change
#   compare the compiled ACLED digest before and after

# Row 12: the export must actually have republished
curl -s -n http://204.168.219.108/grid.zarr/.zattrs | python3 -m json.tool
```

`scripts/measure_allocation_delivery.py` currently reads a local viewpoint parquet. The
remaining half of #553 extends it to read the served store, and that extension must land
**before** the run this file grades.
