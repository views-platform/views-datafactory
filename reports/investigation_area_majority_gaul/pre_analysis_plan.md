# Pre-Analysis Plan: Area-Majority GAUL Assignment

**Registered:** 2026-06-04
**Status:** Pre-registered (hypotheses stated before experiments)
**Investigators:** Simon Polichinel von der Maase, Claude Code

---

## 1. Claim Under Investigation

> Switching from centroid-in-polygon to area-majority spatial join for GAUL assignment will recover the 149 coastal cells currently mapped to `gaul0_code = -1`, restoring their 409,743 missing fatalities to country-level aggregations, without introducing regressions in existing assignments or requiring new dependencies.

This claim is falsifiable. It makes specific predictions about cell counts, fatality recovery, assignment stability, performance, and format compatibility that can each be tested independently.

## 2. Background

PRIO-GRID cells are 0.5-degree squares. The current spatial join tests whether each cell's centroid point falls inside a GAUL polygon. For 149 coastal cells, the centroid falls in water — outside any GAUL polygon — producing `gaul0_code = -1`. Area-majority instead intersects the full cell polygon with all overlapping GAUL polygons and assigns the cell to whichever country covers the largest area of the cell.

This is a standard GIS operation. Tollefsen et al. (2012, Journal of Peace Research) describe area-weighted aggregation as a core PRIO-GRID operation. FAO GAUL documentation (Release Note 02) specifies area-majority as the correct assignment method for gridded data.

### Why pre-registration matters here

This methodology change affects 409,743 fatalities in downstream aggregations. A conflict early warning system cannot change how it counts fatalities without demonstrating that the change was decided on principled grounds — not retrofitted to explain a convenient result. By stating our hypotheses and decision criteria before running the experiments, we commit to accepting the results whether they support the change or not.

## 3. Hypotheses

### H1: Coastal cell recovery

**Prediction:** Area-majority assigns valid GAUL codes (gaul0_code > 0) to all 149 cells that currently have gaul0_code = -1 due to centroid-in-water.

**Falsification criterion:** If any of the 149 cells still has gaul0_code = -1 after area-majority assignment, H1 is falsified.

**Rationale:** These cells are classified as "land" by PRIO-GRID (they appear in the land cell list). Their centroids are in water, but their polygons must overlap at least one GAUL land polygon — otherwise PRIO-GRID would not have classified them as land cells. Area-majority should capture this overlap.

**Risk:** Some cells may be small islands where the GAUL polygon is smaller than the cell's ocean area. In that case, area-majority still assigns the island's country (the largest *land* overlap), but only if we handle the case where the largest overlap is ocean (no GAUL polygon). We may need to define: area-majority among GAUL polygons only, ignoring uncovered (ocean) area.

### H2: No assignment loss

**Prediction:** Every cell that currently has a valid GAUL assignment (gaul0_code > 0) under centroid retains a valid assignment under area-majority. The total count of validly-assigned cells increases by at least 149.

**Falsification criterion:** If any currently-valid cell loses its assignment (gaul0_code becomes -1), H2 is falsified.

**Rationale:** If a cell's centroid is inside a GAUL polygon, that polygon must overlap the cell by at least some area. Area-majority cannot produce a worse result for cells that centroid already handles correctly — it can only reassign them to a different country if another country covers more area.

### H3: Border cell redistribution is a correction

**Prediction:** Approximately 700 cells (estimated ~5.4% of the 13,110 Africa+ME cells) will receive different country assignments under area-majority compared to centroid. These are border cells where the centroid falls in country A but country B covers more of the cell's area.

**Falsification criterion:** H3 is not binary. It is falsified if:
- Fewer than 100 or more than 2,000 cells change assignment (indicates our understanding of the problem is wrong)
- Visual inspection of changed cells reveals systematic errors (e.g., cells deep inland changing assignment, which would indicate a bug)
- The redistributed cells carry an implausible share of total fatalities (>20% would suggest something beyond border corrections)

**Rationale:** This redistribution is the *intended behavior* of area-majority. A cell on the Kenya-Somalia border whose centroid is 0.1 degrees inside Kenya but whose area is 60% Somalia should be assigned to Somalia. This is not a regression — it is a correction of a known limitation of centroid assignment.

### H4: Performance

**Prediction:** The shapely-only computation (STRtree + polygon intersection + area comparison) completes in under 10 minutes for the full 259,200-cell global grid on a standard development machine.

**Falsification criterion:** If computation exceeds 10 minutes on the benchmark machine (the machine that measured 1,218 cells/sec on 500 cells).

**Pre-existing evidence:** Benchmark on 500 real Africa+ME cells measured 1,218 cells/sec. Extrapolation: 259,200 / 1,218 = 213 seconds (~3.5 minutes). Adding GAUL shapefile load time (62.5 seconds), total estimate is ~4.6 minutes.

**Note on relevance:** H4 matters less than H1-H3 and H5. The computation runs once per GAUL version (last gap: 9 years). Even 30 minutes would be acceptable. The 10-minute threshold exists only to confirm the benchmark extrapolation is valid and to document actual performance.

### H5: Format compatibility

**Prediction:** The area-majority output files use the identical `(gid, value)` Parquet schema as the current centroid files. No changes are required in `assemble_grid.py`, `grid_to_country_month.py`, or any consumer code.

**Falsification criterion:** If any consumer code requires modification to read the new files, H5 is falsified.

**Rationale:** Area-majority changes *which country code* is assigned to each cell, not *how the assignment is stored*. The output schema is `gid → gaul0_code`, `gid → gaul1_code`, `gid → gaul2_code` — same as today.

### H6: Square-degree ranking does not change the winner (added 2026-08-21, #465)

**Registered after ADR-039 was accepted**, because the original investigation never considered
projection: neither this plan, `approach_evaluation.md`, nor ADR-039 contains the words *latitude*,
*distortion*, *equal-area* or *EPSG* anywhere. This hypothesis closes that gap.

**The defect.** `scripts/generate_area_majority_gaul.py` builds each cell as
`shapely_box(lon-0.25, lat-0.25, lon+0.25, lat+0.25)` in raw EPSG:4326 (`:94`, `:148`) and ranks
candidates by `cell.intersection(poly).area` (`:103`, `:114`, `:157`, `:165`). **That is square
degrees, not area.** At 60°N one degree of longitude spans about half the ground distance of one
degree of latitude, so a square-degree measure overstates east-west extent by roughly 2×.

**Prediction:** **Zero** cells above 55°N change their winning polygon when intersection slivers are
weighted by `cos(lat)`. The reasoning is that within a single 0.5° cell all candidate polygons sit
in the same narrow latitude band, so `cos(lat)` scales them near-equally and the *ranking* survives
even though the *magnitudes* are all wrong.

**Falsification criterion:** any cell above 55°N whose winning polygon index differs between
square-degree ranking and `cos(lat)`-weighted ranking. One flip falsifies H6.

**Rationale:** the cancellation argument above is the reason nobody caught this in June, and it is
probably right. But it weakens exactly where candidate polygons are **asymmetric in latitude within
the cell** — one polygon occupying the northern strip and another the southern. Those are the cells
that matter and nobody has counted them.

**Risk:** the measurement could report zero flips because it cannot *detect* flips — a script that
computes both rankings identically would be silently vacuous. **The drill in Step 6 exists solely to
rule that out** and is a precondition for believing a null result.

**Scope:** exhaustive above 55°N, not sampled. 18,585 of the 64,742 delivered `land_gaul` cells lie
in that band (28.7%). A sample that found zero could not distinguish "no flips" from "did not look
where the flips are".

## 4. Decision Criteria

These are pre-committed. We will not revise them after seeing results.

| Outcome | Decision |
|---------|----------|
| H1 + H2 + H3 + H5 all hold | **Adopt area-majority.** Performance (H4) is a nice-to-have, not a gate. |
| H1 fails (some coastal cells still unmapped) | **Investigate why.** If failures are island cells with no GAUL polygon overlap, document as a known limitation and adopt for the cells that do work. If failures are widespread, the approach has a fundamental problem — escalate. |
| H2 fails (existing cells lose assignments) | **Do not adopt.** This indicates a bug in the implementation, not a limitation of the method. Fix the bug and re-test. |
| H3 shows implausible redistribution | **Pause and audit.** Visual inspection of outlier cells. If the redistribution is correct (verified against map), proceed. If it reveals systematic errors, investigate. |
| H5 fails (format changes needed) | **Acceptable if changes are minimal** (< 5 lines across all consumers). If the format change is structural, reconsider the approach. |
| **H6 holds — zero flips above 55°N** | **Close the concern and pin the result as a test.** The cancellation argument is then measured rather than assumed, and the delivered FAO artifact is correct as shipped. No change to `generate_area_majority_gaul.py`. |
| **H6 fails — any flips** | **Report the count and the exact gid list; stop there.** Do not correct the artifact and do not contact FAO from this repository. views-postprocessing carries `lookup_version = land_gaul@<our digest>` and their `test_gaul_lookup_fidelity.py` breaks loudly on any correction — that is the intended alarm and theirs to act on. Their `docs/operations/correction_procedure.md` step 4, *who contacts FAO and on what notice*, is **explicitly open**. Fixing before that is settled would put an inconsistent first message in front of a partner. |
| H6's detection drill fails | **Discard the result entirely.** A measurement that cannot detect a flip has not measured anything, and "zero flips" from such a script is worse than no answer because it looks like evidence. |

## 5. Null Outcomes

If the investigation produces null results (the approach doesn't work or isn't worth adopting), the following are valid outcomes:

- **Area-majority is correct but too slow without Rust:** Document performance, defer to Rust implementation (Approach B in approach_evaluation.md). This is not a failure — it's a data point that informs the ADR-030 Rust migration timeline.
- **149 cells include true ocean cells with no GAUL overlap:** Reduce the expected recovery count. Document which cells are truly unrecoverable. This is still progress — it distinguishes "unassigned because of method limitation" from "unassigned because no country claims this area."
- **H6 holds and the answer is boring:** zero flips is the *expected* result and a complete one. It
  converts a plausible argument into a measured fact, retires a question that has been open since
  2026-07-31, and costs nothing further. **Recording a null result is the point of pre-registering
  it** — without this paragraph, "we found nothing" reads like a failed investigation rather than an
  answer.
- **Flips exist but only at admin levels nobody consumes:** a `gaul2` flip with `gaul0` unchanged
  does not move country totals or `land_gaul` membership. Still report it; the severity differs from
  a `gaul0` flip and the report should say which levels moved.
- **Redistribution reveals that centroid was more correct for some cells:** This would be surprising but must be taken seriously. Document the cases and consider a hybrid approach or manual override table.

## 6. Method

### Step 1: Generate area-majority assignments

For each of the 259,200 PRIO-GRID cells:
1. Construct a 0.5-degree polygon: `box(lon - 0.25, lat - 0.25, lon + 0.25, lat + 0.25)`
2. Query the GAUL STRtree for all polygons that intersect the cell
3. For each candidate, compute `cell.intersection(gaul_polygon).area`
4. Assign the cell to the GAUL polygon with the largest intersection area
5. If no GAUL polygon intersects, assign `gaul0_code = -1`

Output: Three Parquet files — `gaul0_code.parquet`, `gaul1_code.parquet`, `gaul2_code.parquet` — each with columns `(gid, value)`.

### Step 2: Validate hypotheses

- H1: Count cells with gaul0_code = -1 in old vs new. Verify the 149 specific cells.
- H2: Check that no cell went from valid (>0) to invalid (-1).
- H3: Count and map cells where old_code != new_code. Visual audit of a sample.
- H4: Time the full computation (already partially benchmarked).
- H5: Run `assemble_grid.py` with new files, verify grid shape and consumer tests.

### Step 3: Before/after comparison

Produce a comparison artifact documenting:
- Cell-level: how many cells changed, from which country to which country
- Fatality-level: how does the country-month aggregation change
- Geographic distribution: map of changed cells

### Step 5: Measure projection sensitivity above 55°N (H6, added 2026-08-21)

1. Enumerate **border cells** above 55°N — cells with more than one candidate polygon. Only these can
   flip. **Report this count before re-ranking**; it is a finding in its own right and nothing in the
   repository currently records it.
2. For each, compute both rankings: square-degree `.area`, and the same slivers weighted by
   `cos(lat)` at each sliver's centroid latitude.
3. Count disagreements. Emit the gid list with old and new codes to a git-tracked JSON here.

**No reprojection, and no new dependency.** The correction is a latitude-only scale factor, so it is
pure numpy over geometry shapely already produces. Note that H6's own issue text proposed `pyproj`;
`pyproj` is not a dependency and its wheels bundle PROJ — the GDAL-family chain ADR-039 rejected in
Alternatives C and D. Using it would contradict the ADR this hypothesis is testing.

### Step 6: Prove the measurement can detect a flip (precondition for Step 5's result)

Construct a synthetic cell whose square-degree winner and `cos(lat)`-weighted winner **differ by
construction** — two candidate polygons asymmetric in latitude — and confirm the script reports it.

**Until this passes, Step 5's output means nothing.** The existing suite cannot substitute:
`tests/test_area_majority.py:121-145` recomputes area-majority in square degrees inside its own
oracles, so all 39 tests are blind to this error class by construction.

### Step 4: Document results

Update this plan's deviations log. Write results into the progress log. Update the draft ADR with actual findings.

## 7. Deviations Log

*This section is intentionally empty at registration time. Deviations from the plan are recorded here as they occur, with dates and rationale.*

| Date | Deviation | Rationale |
|------|-----------|-----------|
| 2026-06-05 | H1 recovery count is 9,481, not 149 | The 149 figure was the Africa+ME subset of unmapped land cells carrying fatalities (#115). Global recovery includes all coastal/island cells worldwide whose centroids fall in water. The hypothesis test checks `> 0`, not `== 149`. H1 survived with a much larger recovery than expected. |
| 2026-06-05 | Centroid baseline has 86,091 rows, not 259,200 | Centroid Parquet files only contain matched cells; unmapped cells are absent (not stored as -1). Area-majority emits all 259,200 cells. Hypothesis tests compare set membership, not array position. |
| 2026-06-05 | H4 total runtime 17.1 min, exceeds 10-min threshold | Per-level computation averages 5.5 min (691-832 cells/sec). The script loads the 45,524-polygon GAUL L2 shapefile three times (once per level). Total wall-clock: 17.1 min. Acceptable for a batch job run once per GAUL version. Per H4 note: "Even 30 minutes would be acceptable." |
| 2026-06-05 | H3 redistribution tested on gaul0 only (368 cells) | gaul1 (1,453) and gaul2 (4,845) redistribution counts are higher, as expected for finer admin levels. The [100, 2000] range was calibrated for gaul0. |
