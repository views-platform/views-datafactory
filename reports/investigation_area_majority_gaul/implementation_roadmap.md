# Implementation Roadmap: Area-Majority GAUL Assignment

**Date:** 2026-06-04
**Issue:** #115 / C-149
**Pre-analysis plan:** [pre_analysis_plan.md](pre_analysis_plan.md)
**Exit criteria:** [definitions_of_done.md](definitions_of_done.md)

---

## Overview

Five sequential phases. Each phase gates the next — do not proceed to Phase N+1 until Phase N's definition of done is met. Estimated total: 4-5 working sessions.

```
Phase 1         Phase 2         Phase 3         Phase 4         Phase 5
Generation  -->  Validation  -->  Integration  -->  Splash Zone  -->  Documentation
Script           H1-H5           Replace files     CM verify        ADR + CIC
(1-2 sessions)   (1 session)     (1 session)       (1 session)      (0.5 session)
```

No phases can run in parallel. Phase 2 validates Phase 1's output. Phase 3 integrates validated output. Phase 4 verifies downstream effects. Phase 5 documents the final decision.

---

## Phase 1: Generation Script

**Goal:** A script that computes area-majority GAUL assignments for all 259,200 PRIO-GRID cells and writes the result as Parquet files.

**Work items:**

1. **Write `scripts/generate_area_majority_gaul.py`** — standalone script (not part of the harvester hot path). Takes GAUL L2 shapefile and PRIO-GRID centroid shapefile as inputs. Outputs three Parquet files: `gaul0_code.parquet`, `gaul1_code.parquet`, `gaul2_code.parquet`.

2. **Algorithm:**
   - Load GAUL L2 polygons from shapefile using `pyshp`, fix invalid geometries with `shapely.make_valid()`
   - Build `STRtree` over GAUL polygons
   - For each PRIO-GRID cell: construct 0.5-degree box, query STRtree for candidates, compute intersection areas, assign to largest
   - Handle edge cases: no overlap (assign -1), single overlap (skip area computation), tied areas (deterministic tiebreaker — lowest gaul code wins)
   - Write provenance ledger entry: GAUL version, method, cell count, content digest

3. **Commit the benchmark script** (`bench_area_majority.py`) alongside the generation script for reproducibility.

4. **Consider vectorized shapely APIs** (`STRtree.query(geom_array)`, `shapely.intersection()`, `shapely.area()`) if per-cell loop performance is insufficient. The benchmark suggests it's fast enough without vectorization, but the option exists.

**Effort estimate:** 1-2 sessions. The core algorithm is simple (the benchmark already implements it). The engineering work is edge cases, provenance, and error handling.

**Key risk:** The benchmark used 500 cells with a sample of GAUL polygons. The full global run may have different performance characteristics (denser polygon regions, more multi-candidate cells). The 10-minute threshold (H4) should catch this.

---

## Phase 2: Validation

**Goal:** Run the pre-analysis plan's hypotheses H1-H5 against the generated output.

**Work items:**

1. **Run the generation script** on the full 259,200-cell global grid. Record actual timing (H4).

2. **Validate H1 (coastal cell recovery):**
   - Load the 149 specific cells that currently have `gaul0_code = -1`
   - Check each one in the new output — does it now have a valid code?
   - For any that remain -1, investigate: is there truly no GAUL polygon overlap?

3. **Validate H2 (no assignment loss):**
   - Compare old centroid files against new area-majority files
   - Assert: every cell with old gaul0_code > 0 still has new gaul0_code > 0

4. **Validate H3 (border cell redistribution):**
   - Count cells where old gaul0_code != new gaul0_code (excluding the 149 recovery cells)
   - Visual audit: pick 10 changed cells, verify on a map that the new assignment is more geographically correct
   - Check fatality share of redistributed cells — should be <20% of total

5. **Validate H5 (format compatibility):**
   - Verify Parquet schema matches: columns `gid` (int) and `value` (float or int)
   - Dry-run `assemble_grid.py` with new files (can be done without full pipeline)

6. **Produce before/after comparison artifact:**
   - Table: cell count, assignment changes by country, fatality redistribution
   - Save to `reports/investigation_area_majority_gaul/before_after_comparison.md` (new file, created during this phase)

7. **Log deviations** in `pre_analysis_plan.md` section 7.

**Effort estimate:** 1 session. Mostly automated checks + manual visual audit of 10 cells.

---

## Phase 3: Integration

**Goal:** Replace centroid-based GAUL files with area-majority files in the data pipeline.

**Work items:**

1. **Replace files in `data/raw/gaul_admin/`:**
   - Back up current centroid files (copy to `data/raw/gaul_admin/centroid_backup/` or similar)
   - Copy area-majority Parquet files into place
   - Update provenance ledger

2. **Run full pipeline assembly:**
   - Execute `scripts/assemble_grid.py`
   - Verify grid shape is unchanged: `(456, 360, 720, N)` where N is current feature count
   - Verify GAUL feature channels contain the new values

3. **Run existing test suite:**
   - `uv run pytest` — all tests must pass
   - Pay special attention to: `test_structural_invariants.py`, `test_model_parity.py`, any GAUL-specific tests

4. **Update `gaul_admin.py` harvester** (if needed):
   - If the harvester currently runs centroid join at harvest time, update it to read the precomputed table instead
   - Or add a `--method` flag: `centroid` (legacy) vs `area-majority` (default)

**Effort estimate:** 1 session.

---

## Phase 4: Splash Zone Verification

**Goal:** Verify that downstream consumers produce correct results with the new assignments.

**Work items:**

1. **CM aggregation verification:**
   - Run `grid_to_country_month.py` with the new grid
   - Compare CM output against the centroid baseline
   - Document the redistribution: which countries gained/lost cells, by how much

2. **Consumer parity tests:**
   - Run `test_consumer_parity.py` (if it exists)
   - Run `test_model_parity.py`
   - The ~5.4% cell redistribution is expected — tests should accommodate this (update tolerances if needed, with documented rationale)

3. **Consumer bridge:**
   - Run `scripts/generate_consumer_data.py`
   - Verify output format is unchanged
   - The `c_id` field (country ID) will have different values for border cells — this is metadata (ADR-025), not a feature

4. **Region lookups:**
   - Verify region subsetting still works (Africa, Middle East, etc.)
   - Some border cells may move between regions — document which ones

5. **Document the splash zone** — add a summary of what changed and by how much to the progress log.

**Effort estimate:** 1 session.

---

## Phase 5: Documentation

**Goal:** Finalize governance documentation. Close the investigation.

**Work items:**

1. **Finalize ADR:**
   - Move `draft_adr_039_area_majority_gaul.md` to `docs/ADRs/039_area_majority_gaul_assignment.md`
   - Update status from "Draft" to "Accepted"
   - Fill in actual results (replace estimates with measurements)

2. **Update CICs:**
   - CIC for `gaul_admin.py` — update spatial join method description
   - CIC for `grid_to_country_month.py` — update the unmapped cell documentation (149 cells are now mapped)
   - CIC for `assemble_grid.py` — note that GAUL codes come from precomputed table

3. **Update risk register:**
   - Close C-149 trigger (or update its status)
   - Register any new concerns discovered during the investigation

4. **Close issue #115** with a summary linking to the ADR and before/after comparison.

5. **Archive investigation directory:**
   - Update README status to "Complete"
   - Final progress log entry

**Effort estimate:** 0.5 session.

---

## Risk Mitigation

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| H1 fails: some coastal cells still unmapped | Low | Investigate individually. May need buffered polygons or manual assignment table. |
| H4 fails: shapely too slow | Very low (benchmark contradicts) | Vectorize with shapely 2.x ufuncs. If still slow, generate table using Rust binary. |
| Test failures during integration | Medium | Expected for tolerance-sensitive tests. Update tolerances with documented rationale, not by suppressing tests. |
| Unexpected consumer breakage | Low | Phase 4 catches this before any deployment. Rollback: restore centroid backup files. |
| GAUL shapefile has projection issues | Very low (EPSG:4326 confirmed) | Verified during benchmark: GAUL L2 is WGS84 lat/lon, same as PRIO-GRID. |
