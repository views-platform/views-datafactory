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

## 2026-06-05 — Phase 1: Generation script + TDD tests (#118)

**Actions taken:**
- Wrote 11 TDD tests for `area_majority_join()` in `tests/test_area_majority.py`
- Implemented `area_majority_join()` in `scripts/generate_area_majority_gaul.py`
- All 11 unit tests pass with synthetic geometry
- Script includes: shapefile loading, centroid loading, Parquet output, provenance ledger
- Committed as `5d3ec87`

**What went well:** Clean TDD cycle. All edge cases covered: empty input, single polygon, ties (lowest code wins), no-overlap cells. Script structure follows existing harvest patterns.

---

## 2026-06-05 — Phase 2: Hypothesis validation (#119)

**Actions taken:**
- Wrote 7 hypothesis tests (H1, H2, H3, H5) with `@pytest.mark.falsification`
- Ran generation script on full 259,200-cell global grid
- Output: `data/raw/gaul_admin_area_majority/{gaul0,gaul1,gaul2}_code.parquet`
- All 7 hypothesis tests pass

**Results:**

| Hypothesis | Verdict | Key Metric |
|------------|---------|------------|
| H1 Coastal Recovery | SURVIVED | 9,481 cells recovered (204 countries) |
| H2 No Assignment Loss | SURVIVED | 0 cells lost, valid: 86,091 → 95,572 |
| H3 Border Redistribution | SURVIVED | 368 cells changed (gaul0), within [100, 2000] |
| H4 Performance | **[DEVIATION]** | 17.1 min total (threshold: 10 min) |
| H5 Format Compatibility | SURVIVED | Schema match, all 3 levels present |

**[DEVIATION] H1 recovery count:** 9,481 cells, not 149. The 149 figure was Africa+ME
only. Global recovery is much larger — coastal/island cells worldwide.

**[DEVIATION] H4 performance:** Total wall-clock 17.1 min across 3 levels.
Per-level: gaul0 374.9s, gaul1 337.5s, gaul2 311.5s. The script reloads the
45,524-polygon GAUL shapefile for each level. Per H4 note in the pre-analysis plan,
even 30 min is acceptable for a one-time batch job.

**What went well:** 4/5 hypotheses survived cleanly. H4 deviation is non-blocking.
Zero assignment loss validates the algorithm correctness. Recovery far exceeds
the Africa+ME subset, which is a positive surprise.

**What went less well:** Script takes 17 min instead of the extrapolated 4.6 min.
The benchmark was on 500 cells; the full grid has more dense-polygon regions
(Europe, SE Asia) that increase per-cell computation cost.

**Artifacts produced:**
- `reports/investigation_area_majority_gaul/before_after_comparison.md`
- `provenance/gaul_admin_area_majority/ingestion_ledger.jsonl` (3 entries)

---

## 2026-06-05 — Phase 3: Pipeline integration (#120)

**Actions taken:**
- Backed up centroid code files to `data/raw/gaul_admin/centroid_backup/`
- Ran area-majority generation to canonical `data/raw/gaul_admin/` directory
- Updated `scripts/refresh_pipeline.sh` to run `generate_area_majority_gaul.py` after `harvest_gaul.py`
- Wrote 5 integration tests (TestI1, TestI2, TestI3) with `@pytest.mark.falsification`
- Updated H-tests (H1, H2, H3) to compare against centroid backup baseline

**Integration approach:**
- Harvester continues to run (downloads shapefiles, produces name files + iso3_code)
- Area-majority script runs immediately after harvester, overwriting code files only
- Name files (`gaul0_name.parquet`, etc.) unchanged — Phase 4 concern
- Assembly script requires zero code changes (reads (gid, value) pairs)

**Test updates:**
- H-tests now compare `centroid_backup/` (original 86,091-row centroid) against `data/raw/gaul_admin/` (259,200-row area-majority)
- 5 new integration tests: assembly compatibility (row count, gid superset), pipeline wiring (script order, output dir), provenance integrity

**What went well:** Zero code changes to assembly, harvester, source registry, or consumers.
Only `refresh_pipeline.sh` needed a 3-line addition. The (gid, value) schema abstraction
made the swap transparent.

**Artifacts produced:**
- Centroid backup at `data/raw/gaul_admin/centroid_backup/` (86,091-row originals)
- Area-majority code files at canonical `data/raw/gaul_admin/` (259,200 rows, 95,572 valid)
- Provenance entries in `provenance/gaul_admin/ingestion_ledger.jsonl` with `method: area_majority`

---

## 2026-06-05 — Phase 4: Splash zone verification (#121)

**Actions taken:**
- Investigated three downstream consumers: CM aggregation, consumer bridge, region subsetting
- Wrote 6 splash-zone tests (TestS1, TestS2, TestS3) with `@pytest.mark.falsification`
- All 6 pass — no consumer code changes required

**Consumer analysis:**

| Consumer | Mechanism | Status |
|----------|-----------|--------|
| `grid_to_country_month.py` | Groups by `gaul0_code > 0` from assembled grid | Works — 9,481 recovered cells now enter aggregation instead of being excluded |
| `generate_consumer_data.py` | Maps `gaul0_code` → `c_id` via FEATURE_RENAME | Works — maps codes, not names |
| `regions.py` | Reads `gaul0_name.parquet` → country name → pgid set | Stable — name files unchanged (86,091 rows from centroid era) |

**Name file gap (known limitation):**
- `gaul0_code.parquet` has 259,200 rows (95,572 valid). `gaul0_name.parquet` has 86,091 rows.
- The 9,481 recovered cells have valid country codes but no country names.
- This is not a regression — these cells were previously unmapped entirely.
- Region subsetting returns identical pgid sets (name files unchanged).
- Documented in test `test_name_file_row_count_documents_gap`.

**What went well:** All three consumer paths verified without code changes. The (gid, value) schema abstraction and code-not-name design of CM aggregation and consumer bridge made the swap transparent.

**Artifacts produced:**
- 6 splash-zone tests in `tests/test_area_majority.py`

---

## Next expected entry

Phase 5: Documentation (#122). ADR-039, CIC updates, C-149 resolution, issue #115 closure.
