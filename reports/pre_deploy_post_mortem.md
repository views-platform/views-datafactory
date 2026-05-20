# Pre-Deploy Post-Mortem: GHS-POP (v1.2.15)

**Date:** 2026-05-20
**Author:** Simon Polichinel von der Maase, Claude Code
**Scope:** GHS-POP R2023A — first raster, non-event data source
**Commits:** 21 (b52481a..1571597), 2026-05-17 to 2026-05-20
**PR:** #51 → development (merged 2026-05-20)

---

## What we built

GHS-POP R2023A population data, from the EU Joint Research Centre, as the third data source in the VIEWS data factory. This is the first non-event, raster-based source — it arrives as GeoTIFF files, not API JSON. It traverses harvest → viewpoint → compilation → assembly, skipping consolidation (single release, nothing to merge).

**Implementation size:**

| Component | Lines | Tests |
|-----------|-------|-------|
| Harvester (`ghspop.py`) | 257 | 462 (19 tests) |
| Viewpoint (`ghspop_v1.py`) | 553 | 934 (37 tests) |
| Compilation (`pregridded_compilation.py`) | 284 | 557 (27 tests) |
| Assembly changes | ~150 | 161 (28 tests, shared) |
| Pipeline scripts | ~1,170 | — |
| Falsification stubs | — | 199 (9 tests across 3 rounds) |
| **Total** | ~2,400 | ~2,300 |

**Final test count:** 910 pass, 0 fail. Up from 821 at v1.2.14.

**Pipeline timing (12 epochs, local):** Harvest 6m04s, Viewpoint 4m56s, Compile 43s. Total ~12 minutes added to pipeline.

---

## What went right

### 1. Phase 0 investigation eliminated the two biggest risks

Before writing any code, we investigated the JRC portal and found that WGS84 (EPSG:4326) data was available at 30-arcsecond resolution. This eliminated two Tier 2 risks from the original plan:

- **Reprojection** — gone. No Mollweide → WGS84 transform. Each PRIO-GRID cell is exactly 60×60 source pixels. Spatial aggregation is `reshape + sum`.
- **GDAL dependency** — gone. No coordinate transformation means no rasterio/GDAL. tifffile (pure Python) reads the GeoTIFF directly.

**Lesson for GHS-BUILT and future raster sources:** Always check if the provider offers WGS84 before assuming reprojection is needed. ADR-030's format survey shows that JRC, CHIRPS, ERA5, FEWS NET, and Copernicus GFM all provide WGS84 or regular lat/lon. Reprojection may be the exception, not the rule.

### 2. WET-before-DRY paid off at the third source

The plan called for writing `compile_pregridded()` as a separate function rather than modifying the existing `compile_grid()`. This was the right call — the two share output format ([T,H,W,C] npy + sidecars) but differ in input handling (pgid lookup vs. lat/lon aggregation). With three sources implemented, the WET patterns are now concrete enough to see what's genuinely shared (C-164 WET inventory documents 7 patterns across 4 layers).

**Lesson:** Don't prematurely abstract at the second source. The third source is where the real patterns emerge. The WET inventory should be consulted before implementing source #4 — several patterns are now ready for extraction.

### 3. ADR-first approach prevented scope creep

Writing ADR-029 (source selection) and ADR-030 (raster tooling) before any implementation forced explicit decisions about scope. "Conflict-adjusted population" was considered and rejected with three specific grounds. "Log-population" was deferred to a future viewpoint variant. This kept the implementation focused on one feature (`ghspop_pop_count`) with clear boundaries.

**Lesson:** Write the ADR before the code. The ADR is where you say no to things.

### 4. The source registry drove downstream integration automatically

Adding `ghspop_pop_count` to `PIPELINE_SOURCES` meant that `verify_remote.py`, `check_health.py`, `preflight.py`, and `get_all_features()` all picked up GHS-POP automatically. No changes to those scripts were needed (beyond updating the expected feature count in tests). The registry pattern from ADR-003 continues to prove its value.

### 5. Consolidation skip was the correct call

GHS-POP R2023A is a single release. There are no vintages to track, no events to merge, no deduplication to perform. Skipping consolidation (consistent with ADR-012: "not all paths traverse all layers") saved ~200 lines of code that would have done nothing. The revisit condition is explicit: add a consolidator when JRC publishes R2024A.

---

## What went wrong

### 1. OOM on the server (C-165) — Tier 1, caught by falsification

**What happened:** tifffile returns float64 arrays. Each epoch is 21384×43202 pixels = ~7.4 GB as float64. `_align_to_globe` allocated a second float64 array of 21600×43200 = ~7.5 GB. Peak RSS: ~22 GB. The server has 8 GB RAM.

**Why it happened:** The plan assumed 21600×43200 dimensions and didn't account for the raw array + aligned array both being in memory simultaneously, both as float64.

**How it was caught:** First falsification audit, probe F2 ("Can the server actually hold this in memory?"). The prediction was FAIL and it was confirmed.

**Fix:** Cast to float32 at read time (`page.asarray().astype(np.float32, copy=False)`). Population data has ~7 significant digits; float32 has ~7.2 digits of precision. Verified with simulation: relative error ~2e-8. Peak RSS dropped from 22 GB to 7.4 GB.

**Lesson for GHS-BUILT:** GHS-BUILT rasters will be the same dimensions as GHS-POP (same JRC GHSL family). Apply float32 cast from day one. More generally: every raster source should estimate peak RSS before implementation. Formula: `(raw_pixels * sizeof(dtype)) + (aligned_pixels * sizeof(dtype))`. If this exceeds server RAM, cast to float32 at read time or process in tiles.

### 2. Source registry gap (C-166) — Tier 2, caught by falsification

**What happened:** `ghspop_pop_count` was implemented in code (viewpoint, compilation, assembly) but never declared in `PIPELINE_SOURCES`. This meant `verify_remote.py` — the post-deploy verification script — was blind to population data. The feature existed in the zarr store but nobody was checking it.

**Why it happened:** The source registry was updated as part of "Phase 5: Assembly + Pipeline Integration" in the plan, but the feature was testable before that phase was complete. The falsification audit probed before Phase 5 was done, catching the gap.

**Lesson:** Add the source registry entry in the same commit as the first implementation file, not as a later integration step. The registry declaration is the birth certificate — everything downstream reads from it.

### 3. Temporal range mismatch — caught by second falsification

**What happened:** `run_ghspop_pipeline.py` used bare `TemporalConfig()` (default `end_year=2024`) while UCDP's `compile_grid.py` uses `--end-year 2026`. GHS-POP produced 432 months, UCDP produced 456 months. Assembly's temporal alignment would zero-fill the last 24 months of population — subtly wrong.

**Why it happened:** The `--end-year` argument was added to `compile_grid.py` and `run_acled_pipeline.py` in earlier versions, but `run_ghspop_pipeline.py` was written from scratch and inherited `TemporalConfig` defaults instead of matching the convention.

**Fix:** Added `--end-year` argument with default 2026 to `run_ghspop_pipeline.py`.

**Lesson:** Every pipeline script that calls `TemporalConfig` must explicitly pass `end_year`. The default (`2024`) is a legacy footgun. Consider updating `TemporalConfig` default to 2026, or — better — making `end_year` a required argument with no default so each caller must be explicit. This is a small ADR-003 compliance gap: the temporal range is inferred from a default rather than declared.

### 4. Silent ZIP fallback violated ADR-011 — caught by code review

**What happened:** When the expected TIF filename wasn't in the downloaded ZIP, the harvester silently picked the first `.tif` file it found. This was a convenience fallback for "JRC might change naming" but violated fail-loud (ADR-011). If JRC ever shipped a ZIP with multiple TIFs or a differently-named file, the harvester would silently ingest the wrong data and record provenance for it.

**Why it happened:** Defensive programming instinct — "handle the edge case gracefully." But in a data pipeline where provenance is mission-critical, "graceful" means "silent data corruption."

**Fix:** Replaced with `ValueError` + ledger entry with `reason` field documenting what was expected vs. found.

**Lesson:** In a fail-loud system, every fallback is a bug. If the system's assumption about upstream data is wrong, the correct response is to stop and tell the operator, not to guess. This applies to all harvesters — audit existing ones for similar patterns.

### 5. Real raster dimensions differed from spec

**What happened:** The plan assumed 21600×43200 pixels (exact PRIO-GRID alignment: 360×60, 720×60). The actual JRC rasters are 21384×43202 — slightly smaller in latitude (polar trim) and 2 extra columns in longitude. The reshape+sum approach failed because the dimensions weren't divisible by 60.

**How it was caught:** First real download during Phase 3 implementation.

**Fix:** `_align_to_globe()` — embed the actual raster into a 21600×43200 array at the correct geographic position using tiepoint/scale tags from the GeoTIFF. Polar rows and trailing columns are zero-padded. The reshape+sum then works on the canonical dimensions.

**Lesson for GHS-BUILT:** GHS-BUILT will likely have the same dimensions as GHS-POP (same GHSL family, same grid). But verify — don't assume. Read one file and print its shape before designing the pipeline. The `_align_to_globe()` function is reusable as-is for any JRC GHSL raster.

### 6. CIC and deployment guide drift — caught by third falsification

**What happened:** After fixing the ZIP fallback, CIC Section 6 (Failure Modes) wasn't updated to list the new `ValueError`. The deployment guide had no GHS-POP mention — operators wouldn't know about ~5.3 GB disk usage or ~12 min added pipeline time.

**Lesson:** Documentation updates must be part of the same commit as the code change, not a separate step. When you add a failure mode, update Section 6. When you add a pipeline step, update the deployment guide. Treat these as the same unit of work.

### 7. Mypy errors in CI — caught late

**What happened:** `tif.pages[0]` returns `TiffPage | TiffFrame` in tifffile's type stubs. We only accessed `.tags` (which `TiffFrame` doesn't have). Also, `blocks.sum(axis=(1,3))` returns `Any` per numpy's stubs. Three mypy errors that passed locally (because we ran mypy on individual files, not the whole project) but failed in CI.

**Fix:** Use `tif.pages.first` (returns `TiffPage`). Annotate the sum result.

**Lesson:** Run `uv run mypy src/` (whole project) before claiming "ready to deploy," not just `mypy` on individual changed files. Add this to the pre-ship checklist.

---

## What we'd do differently next time

### For GHS-BUILT specifically

GHS-BUILT (Built-Up Surface) is the next JRC GHSL source. Based on GHS-POP experience:

1. **Reuse `_align_to_globe()` and `_read_geotiff()`.** Same GHSL family, same raster grid, same GeoTIFF format. The viewpoint builder can import these directly — they're pure functions with no GHS-POP-specific logic.

2. **Reuse `compile_pregridded()`.** The pre-gridded compilation module is source-agnostic. GHS-BUILT viewpoint output should be the same Parquet schema: `(pgid, month_id, value)`.

3. **Consolidation skip again.** Unless GHS-BUILT has multiple releases, skip consolidation for the same ADR-029 reason.

4. **Float32 from the start.** Apply the float32 cast at read time from day one.

5. **Source registry entry first.** Add `SourceEntry(name="GHS-BUILT", features=("ghsbuilt_builtup_area",), ...)` in the first commit.

6. **Temporal range: use `--end-year`.** Match the convention. Don't rely on `TemporalConfig` defaults.

7. **Aggregation function differs.** GHS-POP uses sum (population is a count). GHS-BUILT may want sum (total built-up area) or mean (fraction of cell that is built-up). This is a viewpoint opinion — decide in the ADR, configure in the dataclass.

8. **ADR-031 for GHS-BUILT.** Short ADR — most decisions carry over from ADR-029/030. Focus on what's different: feature naming, aggregation strategy, epoch availability.

### For any future data source

1. **Phase 0 investigation is not optional.** 30 minutes of reading the provider's documentation can eliminate weeks of wrong assumptions (reprojection, authentication, file format). Document findings in the ADR.

2. **Estimate peak RSS before writing code.** `n_pixels × sizeof(dtype) × 2` (raw + working copy). If it exceeds server RAM, plan the mitigation before implementation.

3. **Source registry entry = birth certificate.** Add it in the first commit. Everything downstream reads from it.

4. **Run three falsification rounds.** Not one. The first round catches obvious gaps. The second catches integration issues. The third catches governance drift. Each round should target areas not covered by previous rounds.

5. **CIC + deployment guide in the same commit as the code.** Not as a follow-up. Documentation drift is the most common soft falsification finding across all three rounds.

6. **Check CI before claiming "ready."** Run `uv run ruff check .` + `uv run pytest` + `uv run mypy src/` locally. Don't assume CI will match your local environment.

7. **The temporal range default is a footgun.** Every new pipeline script must explicitly set `end_year`. Consider making it a required parameter.

---

## Checklist for the next raster source

- [ ] Phase 0: Read provider docs. Check CRS, resolution, format, access method, authentication.
- [ ] ADR: Source selection + scope. What's in, what's out. Aggregation strategy.
- [ ] Source registry entry in first commit.
- [ ] Estimate peak RSS. Apply float32 cast if needed.
- [ ] Check if `_align_to_globe()` is reusable or needs modification.
- [ ] Check if `compile_pregridded()` handles the output schema.
- [ ] Pipeline script with explicit `--end-year`.
- [ ] CIC for the new config dataclass.
- [ ] Deployment guide paragraph (disk, timing, credentials).
- [ ] `refresh_pipeline.sh` updated.
- [ ] Three falsification rounds before tagging.
- [ ] `uv run mypy src/` clean (not just individual files).
- [ ] CI green (or failures confirmed pre-existing).

---

## Risk register entries from this implementation

All resolved as of v1.2.15:

| ID | Tier | Issue | Resolution |
|----|------|-------|------------|
| C-165 | 1 | OOM: 22 GB peak on 8 GB server | float32 cast, peak → 7.4 GB |
| C-166 | 2 | Source registry gap — verify_remote.py blind | Added SourceEntry to PIPELINE_SOURCES |
| C-167 | 4 | audit_ghspop/ not in .gitignore | Added to .gitignore |
| C-161 | 4 | Harvester failure-path provenance untested | Added tests |
| C-162 | 1 | PGID mapping untested | Added direct correctness test |
| C-163 | 2 | Raster truncation on non-divisible dimensions | _align_to_globe() handles alignment |
| C-164 | — | WET inventory (7 patterns across 4 layers) | Documented, defer extraction to source #4 |

---

## Timeline

| Date | Milestone |
|------|-----------|
| 2026-05-17 | ADR-029 (source selection), ADR-030 (raster tooling), Python 3.12 bump |
| 2026-05-17 | Phase 1: Harvester implementation + tests |
| 2026-05-18 | Phase 3: Viewpoint (spatial aggregation + temporal interpolation) |
| 2026-05-18 | Harvester test review → C-161 resolved |
| 2026-05-19 | CICs for GhsPopConfig, GhsPopViewpointConfig |
| 2026-05-19 | Phase 4: Pre-gridded compilation + WET inventory |
| 2026-05-19 | Phase 5: Assembly + pipeline scripts |
| 2026-05-19 | Real raster alignment fix (_align_to_globe) |
| 2026-05-19 | Switch from step to linear interpolation |
| 2026-05-19 | Visual audit (10 plots, all pass) |
| 2026-05-20 | Falsification round 1: OOM, source registry, gitignore |
| 2026-05-20 | Falsification round 2: ADR drift, --end-year, version bump |
| 2026-05-20 | Falsification round 3: CIC drift, deployment guide |
| 2026-05-20 | All fixes applied. PR #51 merged → development |

4 days from ADR to merged PR, including 3 falsification rounds.
