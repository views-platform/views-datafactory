# Post-mortem: CM aggregation silently excludes 603 unmapped GAUL cells

**Date:** 2026-04-30
**Severity:** Tier 2 (High — silent data gap, no error signal)
**Status:** Detected, documented, test-guarded. Runtime warning not yet implemented.
**Risk register:** C-149

---

## Timeline

| When | What |
|------|------|
| 2026-04-21 | `grid_to_country_month()` implemented (C-125 resolution). Filter `country_ids > 0` added to exclude ocean cells. |
| 2026-04-21 | `assemble_grid.py` assigns `gaul0_code = -1.0` to cells not matched by GAUL spatial join. This was documented in ADR-025 line 85 ("GAUL codes include -1 for ocean or unassigned cells") but the downstream impact on CM aggregation was not analyzed. |
| 2026-04-30 | Pipeline verification audit. Tests comparing factory PGM totals against factory CM totals fail with max monthly diff of 2,688 fatalities and 4% global sum gap. |
| 2026-04-30 | Root cause identified: 603 cells in `africa_me_legacy` have `gaul0_code = -1` (coastal/island cells). These carry 45,593 sb fatalities across 435 months. CM aggregation drops them because it filters on `gaul0_code > 0`. |
| 2026-04-30 | Tests fixed to account for the structural gap. C-149 registered. Documentation updated (CIC, ADR-025, consumer guide, transition guide). |

---

## Root cause

The GAUL spatial join (`gaul_admin.py`) assigns country codes by testing whether each PRIO-GRID cell centroid falls inside a GAUL polygon. Cells whose centroids are in the ocean — even though they're classified as "land" cells in the PRIO-GRID definition — get no match and are assigned `gaul0_code = -1` during assembly.

`grid_to_country_month()` filters on `country_ids > 0` to exclude ocean cells. This is correct for true ocean cells (global grid minus land), but it also excludes the 603 land cells that have conflict events but no GAUL match. The filter cannot distinguish "ocean cell with no events" from "coastal land cell with events but no country polygon match."

The 603 cells are distributed along coastlines: South Africa's coast, East African islands, Gulf of Aden, Red Sea coast, and Mediterranean coast. Some carry significant conflict (port cities, maritime zones).

---

## Impact

| Metric | Value |
|--------|-------|
| Affected cells | 603 / 13,110 in africa_me_legacy (~4.6% of cells) |
| Affected fatalities (sb) | 45,593 / 1,202,856 total (~3.8%) |
| Affected fatalities (ns) | 6,012 / 183,626 total (~3.3%) |
| Affected fatalities (os) | 7,986 / 1,126,777 total (~0.7%) |
| Max single-month gap (sb) | 2,688 fatalities |
| Models affected | shining_codex (CM/global/N-BEATS) — trains on `output_format="country_month"` |
| Models unaffected | heavy_freighter, heavy_strider, light_strider, bright_starship — all PGM models that use `output_format="dataframe"` |

The gap is **systematic and silent**. A CM model trained on factory data sees ~4% fewer state-based fatalities than the same model trained on PGM data. No warning is emitted. The model cannot distinguish "less conflict" from "missing data."

---

## Why this wasn't caught earlier

1. **Per-cell parity tests pass.** The existing `test_consumer_parity.py` checks per-cell mismatch rates. Since the 603 cells are simply absent from CM output (not present with wrong values), they don't register as mismatches.

2. **C-125 focused on the happy path.** When CM aggregation was implemented, the filter `country_ids > 0` was correct for its stated purpose (exclude ocean). The edge case of land cells with `gaul0_code = -1` was mentioned in ADR-025 but not connected to the aggregation impact.

3. **No PGM↔CM consistency test existed.** Before this verification audit, no test compared PGM totals against CM totals from the same underlying data.

---

## What was done

### Immediate (2026-04-30)

- Added 58-test verification suite across 3 layers (structural invariants, gold set parity, pipeline consistency)
- CM parity tests explicitly account for the unmapped cell gap
- Internal consistency test (`test_pgm_cm_internal_consistency`) filters PGM to `gaul0_code > 0` before comparing with CM, proving the aggregation itself is correct
- C-149 registered in the risk register (Tier 2)
- CIC for `grid_to_country_month` updated to document the exclusion and its magnitude
- ADR-025 updated with "Unmapped cells" subsection
- Consumer data guide updated with CM aggregation caveat section
- Viewser transition guide updated with CM gap note

### Remaining (tracked by C-149)

- Emit runtime warning when CM aggregation drops cells that carry nonzero event values
- Expose metadata listing excluded pgids and their event totals
- Consider improving GAUL spatial join to capture more coastal cells (buffered centroids or polygon-edge matching)

---

## Lessons

1. **Aggregate checks catch what per-cell checks miss.** C-139 identified this pattern in the stale-zarr incident. This finding reinforces it: per-cell parity can be 100% while aggregate totals diverge by 4%.

2. **Filtering operations need impact analysis.** The `country_ids > 0` filter was correct in isolation but its data impact was never quantified. Any filter that drops rows should be accompanied by a measurement of what is lost.

3. **Edge cases at spatial boundaries are real.** PRIO-GRID "land" cells and GAUL "land" polygons don't perfectly align. The grid uses a fixed 0.5-degree raster; GAUL uses vector polygons. Centroids near coastlines can easily fall in the ocean. This is a fundamental property of raster-vector misalignment, not a bug.

4. **Internal consistency tests are high value.** The most diagnostic test was `test_pgm_cm_internal_consistency`: load PGM and CM from the same factory, same region, same time range, and assert totals match. This is cheap to write and catches a whole class of aggregation issues.
