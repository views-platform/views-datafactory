# Annual release supersession — measured impact (#594, #595)

**Date:** 2026-11-17
**Branch:** `fix/595-annual-release-supersedes`
**Store:** scratch consolidated store built from `data/raw/` plus the production
`ucdp_ged_v26.1_1989_2025.parquet` (416,968 rows, digest matches the production
consolidation ledger). 2,713,398 rows, 164 sources, against production's 2,891,590 and
177 — production holds more recent candidate and `.9` months, which do not affect any
year an annual release covers.
**Profile:** `kgi_kti_activity` (production's).

## What was measured

Two viewpoints built from the identical store, one with the fix and one without, by
stashing the source change. The before-build is therefore a faithful reproduction of
what production publishes today.

## Result: exact agreement with UCDP release 26.1

Global fatality totals, all three violence types:

| year | before (= published today) | after | UCDP v26.1 | after − UCDP |
|---|---:|---:|---:|---:|
| 2022 | 318,026 | **317,936** | 317,936 | **0** |
| 2023 | 170,820 | **170,432** | 170,432 | **0** |
| 2024 | 190,609 | **188,209** | 188,209 | **0** |

Broken out by violence type, every one of the nine cells also agrees exactly:

| year | type | before | after | UCDP v26.1 |
|---|---|---:|---:|---:|
| 2022 | state-based | 285,348 | 285,324 | 285,324 |
| 2022 | non-state | 20,159 | 20,093 | 20,093 |
| 2022 | one-sided | 12,519 | 12,519 | 12,519 |
| 2023 | state-based | 139,528 | 139,149 | 139,149 |
| 2023 | non-state | 19,581 | 19,578 | 19,578 |
| 2023 | one-sided | 11,711 | 11,705 | 11,705 |
| 2024 | state-based | 157,628 | 155,255 | 155,255 |
| 2024 | non-state | 18,248 | 18,234 | 18,234 |
| 2024 | one-sided | 14,733 | 14,720 | 14,720 |

The before column reproduces the figures in the served store and in the mail sent on
2026-11-17, so the baseline is faithful and the agreement is not an artefact of the
scratch build.

**Ukraine 2024: 100,601 → 98,352**, the acceptance criterion in #595, exactly.

## Total movement

**321 events, 4,939 deaths**, removed across **24 years** and **45 country-years**.
These are events present in UCDP v25.1 and withdrawn in v26.1 — merged, reclassified or
dropped during UCDP's own revision — which our append-only store kept and the viewpoint
had no rule to discard.

Larger than the 2,878 reported in #594, because that measurement covered only 2022–2024,
the span for which both releases were in hand at the time.

### Every country-year moving by 50 deaths or more

| country | year | before | after | change |
|---|---|---:|---:|---|
| Ukraine | 2024 | 100,601 | 98,352 | −2,249 (−2.24%) |
| United States of America | 2010 | 2,205 | 752 | −1,453 (−65.90%) |
| Colombia | 1999 | 4,259 | 3,974 | −285 (−6.69%) |
| Ukraine | 2023 | 76,711 | 76,485 | −226 (−0.29%) |
| Mexico | 2010 | 5,677 | 5,547 | −130 (−2.29%) |
| Palestine | 2023 | 8,708 | 8,612 | −96 (−1.10%) |
| Somalia | 2024 | 2,422 | 2,345 | −77 (−3.18%) |
| DR Congo | 2022 | 5,352 | 5,286 | −66 (−1.23%) |
| Israel | 2023 | 18,985 | 18,928 | −57 (−0.30%) |

36 further country-years move by less than 50 deaths.

Blast radius: 21 country-years move by more than 1%, 8 by more than 5%, 7 by more
than 10%.

### The 66% drop in "United States 2010" is correct, and is two defects meeting

It is four Juárez–Sinaloa cartel events, UCDP country **Mexico**, each ~250–265 deaths,
all at PRIO-GRID cell 175108. UCDP withdrew them in v26.1, so removing them is right.

They appear under the United States because cell 175108 straddles the border and our
area-majority assignment gives it to the USA — the mechanism in #592 and #593. That
mis-attribution is untouched by this change and remains open.

## Verification performed

- Full suite: **2,626 tests, 0 failures, 0 errors** (counted from JUnit XML, not from
  the exit status — this repo's conftest withholds the summary line, and C-345 warns
  that a piped status can hide a SIGKILL).
- `ruff check .`, `mypy src/` (91 files), `bash docs/validate_docs.sh` — all clean.
- The two regression tests in `tests/test_viewpoint.py` were confirmed to fail with the
  source change reverted and pass with it.
- Conservation held: `n_read == n_input + n_stale` in both builds.

## Not addressed here

- The country assignment that puts Mexican deaths in the United States and Kursk deaths
  in Sumy (#592, #593).
- `where_prec == 5` polygon selection (#593).
- The spatial weight map having no time dimension (noted on #593).
- `docs/` cannot cite the UCDP viewpoint builder by symbol, because
  `src/datafactory_viewpoint/builders/` is missing from the citation guard's search
  roots. Found while writing the ADR-023 amendment; not fixed here.

## Found by review, after the measurement above

`/code-review` ran on this branch before it merged and found two defects in the fix
itself. Both are recorded here because the measurement above was already complete when
they were found, and neither changes any number in it.

- **The span bound is upper-only (#598).** An older release's rows survive if they end
  *after* the latest release's coverage, and not if they begin *before* it. A future
  release starting later than its predecessor would delete the earlier history. Confirmed
  by probe: with a release covering 2000-2026 alongside one covering 1989-2024, a 1990
  event disappears. A symmetric `min(date_start)` bound was tried and reverted — it
  broke all three regression tests above, correctly, because in a sparse store every
  older row falls before the latest release's first event. The declared span is in the
  harvest filename and discarded at consolidation, so the real fix needs it carried into
  the store. The code comment and the ADR amendment now state the bound is one-sided.
- **A non-numeric annual version would delete the real release (fixed here).**
  `_parse_version` maps an unorderable string to `(0,)`, which sorts below every real
  version, so a malformed new release would lose to its predecessor and have its own
  rows dropped as superseded. Supersession is now refused outright when any annual
  version is non-numeric, with a warning. Guarded by
  `test_non_numeric_annual_version_blocks_supersession`.
- **A short harvest of the newest release is now destructive (C-371).** The rule cannot
  distinguish an event UCDP withdrew from one our harvest missed. Before this change a
  shortfall left the old rows in place; after it, the shortfall deletes them. Registered,
  not fixed.

All guards in this change were sabotaged and confirmed to go red, and from the third round
onward the **whole enclosing test class** was run under each mutation rather than the tests
believed to cover it — see C-370, where selecting a subset is what let a decorative test through.

A `/falsify` audit then found one more defect, in the fix itself: a null `date_end` in the newest
annual release made this step delete **every** annual row in silence, its own release included,
with conservation balancing and nothing logged above INFO. On `development` the same input raises
`TypeError`. The step now stands aside when any annual `date_end` is null, which restores that
loud failure rather than inventing a second error path. Real data has zero nulls across all
384,918 rows, so it was never reachable, but ADR-023 §2 documents a missing `date_end` as
possible. Guarded by `test_null_annual_date_end_does_not_delete_silently`.
