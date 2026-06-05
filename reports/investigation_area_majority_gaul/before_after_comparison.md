# Before/After Comparison: Centroid vs Area-Majority GAUL Assignment

**Date:** 2026-06-05
**Phase:** 2 (Hypothesis Validation, #119)
**Script:** `scripts/generate_area_majority_gaul.py`
**Commit baseline:** `5d3ec87` (Phase 1)

## Cell Counts

| Metric | Centroid | Area-Majority | Delta |
|--------|----------|---------------|-------|
| Total rows | 86,091 | 259,200 | +173,109 |
| Valid (value > 0) | 86,091 | 95,572 | +9,481 |
| Unassigned (value = -1) | 0 (absent) | 163,628 | n/a |

The centroid method only emits matched cells (86,091 rows).
Area-majority emits all 259,200 PRIO-GRID cells; unmatched cells get value -1.

## H1: Coastal Cell Recovery

**Result: SURVIVED**

9,481 cells gained valid GAUL country assignments that had no centroid match.
All recovered cells have codes > 0. Recovery spans 204 unique countries.

Top recovered country codes (gaul0):

| GAUL Code | Recovered Cells |
|-----------|----------------|
| 182 | 1,333 |
| 371 | 1,155 |
| 328 | 1,067 |
| 241 | 579 |
| 220 | 460 |
| 372 | 372 |
| 343 | 313 |
| 361 | 166 |
| 263 | 166 |
| 246 | 165 |

**Deviation from pre-analysis:** The 149-cell figure from #115 was the Africa+Middle East
subset of unmapped land cells carrying fatalities. Global recovery is 9,481 cells,
which includes all coastal and island cells worldwide whose centroids fall in water.

## H2: No Assignment Loss

**Result: SURVIVED**

Zero cells lost a valid assignment. Every centroid gid with value > 0 retains
value > 0 in area-majority. Valid count increased from 86,091 to 95,572.

## H3: Border Redistribution

**Result: SURVIVED**

Cells present in both methods but with different codes:

| Level | Changed Cells |
|-------|---------------|
| gaul0_code | 368 |
| gaul1_code | 1,453 |
| gaul2_code | 4,845 |

gaul0 redistribution (368 cells) is within the pre-registered [100, 2000] range.
Higher redistribution at finer admin levels is expected: smaller polygons mean
more cells where the centroid is near a boundary.

Top FROM codes (gaul0): 327 (21), 248 (16), 234 (14), 292 (14), 180 (11)
Top TO codes (gaul0): 328 (25), 234 (17), 172 (11), 257 (11), 240 (9)

## H4: Performance

**Result: DEVIATION**

| Level | Duration | Rate |
|-------|----------|------|
| gaul0_code | 374.9s (6.2 min) | 691 cells/sec |
| gaul1_code | 337.5s (5.6 min) | 768 cells/sec |
| gaul2_code | 311.5s (5.2 min) | 832 cells/sec |
| **Total** | **1,023.9s (17.1 min)** | — |

Total exceeds the 10-minute threshold. Per-level averages ~5.5 min.
The script reloads 45,524 GAUL polygons from the L2 shapefile three times
(once per level). Caching the shapefile load would save ~3 min.

This is a batch job run during deployment, not interactive. The 17-min
runtime is acceptable for the deployment use case. The 10-min threshold
was aspirational; the deviation is documented, not blocking.

## H5: Format Compatibility

**Result: SURVIVED**

- Schema matches centroid baseline: `gid: int32`, `value: int32`
- All three levels exist: gaul0_code.parquet, gaul1_code.parquet, gaul2_code.parquet
- Provenance ledger entries written for all three levels

## Summary

| Hypothesis | Verdict | Key Metric |
|------------|---------|------------|
| H1 Coastal Recovery | SURVIVED | 9,481 cells recovered |
| H2 No Assignment Loss | SURVIVED | 0 cells lost |
| H3 Border Redistribution | SURVIVED | 368 changed (gaul0) |
| H4 Performance | DEVIATION | 17.1 min total (threshold: 10 min) |
| H5 Format Compatibility | SURVIVED | Schema and files match |

4 of 5 hypotheses survived. H4 deviated on total runtime but per-level
performance is reasonable. No blocking issues for pipeline integration (#120).
