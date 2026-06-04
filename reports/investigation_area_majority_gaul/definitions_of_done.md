# Definitions of Done: Area-Majority GAUL Assignment

**Date:** 2026-06-04
**Roadmap:** [implementation_roadmap.md](implementation_roadmap.md)
**Pre-analysis plan:** [pre_analysis_plan.md](pre_analysis_plan.md)

---

## Phase 1: Generation Script

- [ ] `scripts/generate_area_majority_gaul.py` exists and runs without error
- [ ] Script produces three Parquet files: `gaul0_code.parquet`, `gaul1_code.parquet`, `gaul2_code.parquet`
- [ ] Each file contains columns `gid` (int) and `value` (int or float)
- [ ] Files cover all 259,200 PRIO-GRID cells (no missing gids)
- [ ] Provenance ledger entry written with: GAUL version, method="area-majority", cell count, content digest
- [ ] Benchmark script committed alongside generation script
- [ ] Edge cases handled: no-overlap cells assigned -1, single-overlap cells skip area computation, tied areas resolved deterministically

## Phase 2: Validation

- [ ] H1 evaluated: result documented (how many of 149 coastal cells recovered)
- [ ] H2 evaluated: result documented (no cells lost valid assignments)
- [ ] H3 evaluated: result documented (border cell count, visual audit of 10 cells)
- [ ] H4 evaluated: actual timing recorded
- [ ] H5 evaluated: Parquet schema verified identical to centroid files
- [ ] Before/after comparison artifact committed to investigation directory
- [ ] Deviations from pre-analysis plan logged in `pre_analysis_plan.md` section 7
- [ ] All hypothesis results recorded in progress log

## Phase 3: Integration

- [ ] Area-majority Parquet files placed in `data/raw/gaul_admin/`
- [ ] Centroid files backed up (not deleted)
- [ ] `assemble_grid.py` produces correct grid shape with new files
- [ ] `uv run pytest` passes (all tests green)
- [ ] Provenance ledger updated
- [ ] `gaul_admin.py` harvester updated if applicable

## Phase 4: Splash Zone Verification

- [ ] CM aggregation runs with new assignments
- [ ] Redistribution documented: which countries gained/lost cells, magnitude
- [ ] Consumer parity tests pass (tolerances updated if needed, with documented rationale)
- [ ] Consumer bridge (`generate_consumer_data.py`) output format unchanged
- [ ] Region subsetting verified
- [ ] No silent data loss: total fatalities across all countries >= previous total

## Phase 5: Documentation

- [ ] ADR-039 finalized in `docs/ADRs/039_area_majority_gaul_assignment.md`, status "Accepted"
- [ ] CICs updated: `gaul_admin.py`, `grid_to_country_month.py`, `assemble_grid.py`
- [ ] C-149 updated in risk register (resolved or trigger updated)
- [ ] Issue #115 closed with summary
- [ ] Investigation directory README status updated to "Complete"
- [ ] Final progress log entry

---

## Overall Definition of Done

The investigation is complete when:

1. All Phase 1-5 checklists above are satisfied
2. No hypothesis failure (H1-H5) remains unexplained — every failure has a documented rationale and either a fix or a documented known limitation
3. The ADR is in `docs/ADRs/` with status "Accepted"
4. The pipeline runs end-to-end with area-majority assignments and produces the expected grid
5. The deviations log in the pre-analysis plan accounts for every change from the original plan
