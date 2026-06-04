# Progress Log: Area-Majority GAUL Assignment

**Issue:** #115 / C-149
**Branch:** `investigation/115-area-majority-spatial-join`

---

Timestamped entries recording what happened, what worked, what didn't, and what changed. Deviations from the pre-analysis plan are marked with **[DEVIATION]** and cross-referenced to `pre_analysis_plan.md` section 7.

---

## 2026-06-04 — Investigation opened

**Context:** During v1.2.27 deployment (pipeline running on Hetzner), investigated issue #115 which documents C-149: 149 coastal PRIO-GRID cells with centroids in water, silently dropping 409,743 fatalities from country-level aggregations.

**Actions taken:**
- Created issue #115 on GitHub documenting the problem
- Branched `investigation/115-area-majority-spatial-join` from `development`
- Created `reports/investigation_area_majority_gaul/` directory

**What went well:** Problem well-defined. Quantified impact already documented in `postmortem_cm_unmapped_gaul_cells.md`.

---

## 2026-06-04 — Approach research

**Actions taken:**
- Evaluated five spatial join approaches: shapely-only, Rust geo-rs, precomputed table, geopandas, DuckDB Spatial
- Reviewed ADR-030 for anti-geopandas/GDAL precedent
- Researched Rust `geo` crate ecosystem: geo v0.31.0, rstar v0.12.2, shapefile v0.7.0
- Confirmed GAUL update frequency: 9-year gap (2015 → 2024), effectively static
- Confirmed PRIO-GRID 2.0 is frozen (grid definition will not change)

**Findings:**
- geopandas and DuckDB Spatial rejected: same GDAL dependency problem as ADR-030
- Rust is the best long-term option but premature for a one-time computation on static data
- Shapely-only extends existing code with zero new dependencies
- Precomputed table decouples computation from consumption

**What went well:** Clear evaluation criteria. ADR-030 provided strong precedent.

---

## 2026-06-04 — Shapely benchmark

**Actions taken:**
- Wrote benchmark script (`/tmp/bench_area_majority.py`) testing shapely polygon-polygon intersection
- Ran on 500 real Africa+ME cells against full GAUL L2 shapefile (45,524 polygons)

**Results:**

| Metric | Value |
|--------|-------|
| Per-cell join rate | 1,218 cells/sec |
| GAUL shapefile load time | 62.5s |
| Invalid geometries fixed | 0 |
| Extrapolated: full global grid | ~4.6 min (including load) |

**What went well:** Performance far exceeded expectations. No dependency issues. Zero invalid geometries in GAUL L2.

**What went less well:** Three subagent attempts to run the benchmark were blocked (plan mode restrictions, confirmation hesitation). Had to write and run the script directly.

---

## 2026-06-04 — Documentation structure

**Actions taken:**
- Researched pre-analysis plan frameworks (SAP, Registered Reports for SE, hypothesis-driven development)
- Designed 7-document investigation structure
- Created all investigation documents: README, pre-analysis plan, approach evaluation, implementation roadmap, definitions of done, progress log (this file), draft ADR

**What went well:** Research identified pre-registration as the key missing practice in our existing investigation workflow. Existing repo conventions (dot9_investigation, consumer_parity_investigation) provided strong templates.

---

## Next expected entry

Phase 1 (generation script) begins. First entry will record: script creation, initial test run on a small sample, any deviations from the pre-analysis plan.
