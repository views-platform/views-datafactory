# Investigation: ACLED offset → cursor pagination

**Issue:** #487 (migration), #488 (the short-harvest gap it surfaced)
**Branch:** `feat/acled-cursor-pagination`
**Risk register:** C-153 (Tier 3 — no server-declared total; this change replaces the heuristic it names), C-359
**Started:** 2026-10-10
**Investigators:** Simon Polichinel von der Maase, Claude Code
**Status:** Complete — parity confirmed 2026-10-10. H1/H2/H3/H5/H6 resolved, H4 negative. See [`findings.md`](findings.md).

---

## Problem

ACLED will remove offset (`&page=N`) pagination on **27 October 2026**. Our harvester uses it.

The migration itself is small — one loop in `fetch_paginated()` in
`src/datafactory_harvester/sources/acled.py`. What makes it worth pre-registering is the shape of
the failure it risks. The change deletes the loop's termination condition and replaces it with a
different one, and a termination bug in a harvester does not crash: it returns *fewer events* and
records them as a success. Nothing in this repository compares a harvest's event count against the
previous harvest of the same year (#488), so a truncated harvest would reach the assembled grid
silently.

ADR-027 exists because that already happened once, on UCDP: `page_size=50000` made the API return
335,918 of 384,918 events while the harvest reported success
(`reports/post_mortems/2026-04-25_stale_zarr_store.md`).

So "the tests pass" is not sufficient evidence that the migration is correct. The claim that needs
proving is a parity claim — that a cursor walk and an offset walk over the same slice return the
same data — and it can only be proven **before 27 October**, while both methods still work.

## Contents

- [`pre_analysis_plan.md`](pre_analysis_plan.md) — the hypotheses, the falsification criteria and
  the pre-committed decision table, registered before any implementation code
- [`findings.md`](findings.md) — the answer, written after the measurement
- [`parity_quarter.json`](parity_quarter.json) — the headline result: 98,636 events, a full
  quarter, all countries, at production's own `page_size=5000`, identical both ways
- [`parity.json`](parity.json) — the first run: 7,609 events, one week, `limit=1000`, identical
  both ways. Superseded as the headline but kept: it is a second independent measurement, taken
  two days earlier at a different page size
- [`parity_fixture_slice.json`](parity_fixture_slice.json) — the narrow run (84 events, Somalia)
  that produced the committed replay fixtures. Separate because an ACLED event is ~1.4 KB, so the
  headline slice would have been a 10 MB fixture per walk — good evidence, bad fixture.
- [`../../notebooks/acled_cursor_parity.ipynb`](../../notebooks/acled_cursor_parity.ipynb) — the
  human-readable argument, committed with outputs. Reads only the files above and the recorded
  envelopes; makes no network request, so it still renders after 27 October. It recomputes the
  content digest from the raw envelopes rather than reprinting the reported one, and section 6
  lists what the evidence does **not** establish.

## Methodology Note

This investigation uses pre-registration. The pre-analysis plan must be committed before any
implementation code is written, so that "parity held" is a result rather than a rationalisation.

Two things follow from that, and both are recorded in the plan rather than assumed:

1. **The decision table commits to both outcomes before either is observed** — including what we do
   if parity fails, which is the branch nobody plans for.
2. **The measurement must prove it can detect a difference before its null result is believed.** A
   parity script that reports "identical" without a detection drill is indistinguishable from one
   that compares a walk against itself. The drill is a precondition in the script, not an optional
   flag — the same construction as `scripts/verify_area_majority_projection.py`.
