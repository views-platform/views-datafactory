# Sprint Plan: WET Extraction + Harvest Correctness (C-164, C-223, C-184/C-185/C-186)

**Date:** 2026-05-30
**Status:** Ready for execution
**Base branch:** `development`
**Safety checkpoint:** `a2b798f` (if everything goes sideways: `git reset --hard a2b798f`)
**GitHub issues:** #73 -- #82
**Register entries:** C-164 (WET debt), C-223 (bounded memory), C-184/C-185 (cache digest), C-186 (shapefile outcome), C-230 (script layer untested)
**Estimated effort:** 7 working days across 3 sprints

---

## PR Dependency Graph

```
Sprint A: WET Extraction                Sprint B: Bounded Memory    Sprint C: Harvest Correctness
========================                ========================    =============================

PR-1 (#73)                              PR-7 (#79)                  PR-9 (#81)
Config validators                       open_memmap()               Cache digest verification
     |                                       |                           |
     v                                       v                           v
PR-2 (#74) -----> PR-3 (#75)            PR-8 (#80)                  PR-10 (#82)
Harvest chartest   HarvestRunner        Pre-flight checks           Shapefile outcome vocab
                                                                        
PR-4 (#76) -----> PR-5 (#77)
Pipeline chartest  PipelineRunner

PR-6 (#78)
Viewpoint scaffolding

Parallelism:
  Sprint A: PR-1, PR-2, PR-4, PR-6 can start simultaneously
            PR-3 blocked by PR-2
            PR-5 blocked by PR-4
  Sprint B: PR-7 then PR-8 (sequential)
  Sprint C: PR-9, PR-10 can start simultaneously
  Cross-sprint: B and C can start after A merges
```

---

## Sprint A: WET Extraction (4 working days)

### PR-1: Config Validation Utilities (#73)

**Branch:** `refactor/config-validators`
**Base:** `development`
**Blocks:** Nothing (independent)
**Parallel with:** PR-2, PR-4, PR-6

**Files created:**
- `src/datafactory_harvester/validation.py` -- shared validator functions
- `tests/test_config_validation.py` -- unit tests for validators

**Files modified:**
- `src/datafactory_harvester/sources/ucdp_annual.py` -- replace inline validators
- `src/datafactory_harvester/sources/ucdp_candidate.py` -- replace inline validators
- `src/datafactory_harvester/sources/ucdp_dot9.py` -- replace inline validators
- `src/datafactory_harvester/sources/acled.py` -- replace inline validators
- `src/datafactory_harvester/sources/ghspop.py` -- replace inline validators
- `src/datafactory_harvester/sources/ghsbuilts.py` -- replace inline validators
- `src/datafactory_harvester/sources/priogrid_static.py` -- replace inline validators
- `src/datafactory_harvester/sources/gaul_admin.py` -- replace inline validators
- `src/datafactory_harvester/sources/vdem.py` -- replace inline validators
- `src/datafactory_harvester/sources/shdi.py` -- replace inline validators

**Pre-merge gate:**
```bash
uv run ruff check .
uv run pytest tests/test_config_validation.py -v
uv run pytest tests/ -q                          # full suite, no regressions
```

**Merge criteria:**
- All 10 harvester configs use shared validators
- Existing config tests still pass (green)
- New tests cover: valid config, each invalid field, edge cases (timeout=0, timeout=1)
- No behavioral change in any harvester

---

### PR-2: Harvest Script Characterization Tests (#74)

**Branch:** `test/harvest-script-characterization`
**Base:** `development`
**Blocks:** PR-3 (HarvestRunner extraction)
**Parallel with:** PR-1, PR-4, PR-6

**Files created:**
- `tests/test_harvest_scripts.py` -- characterization tests for all 9 harvest scripts

**Files modified:** None (test-only PR)

**What the tests must cover:**
- `--help` exits 0 for each script
- `--force` flag is accepted
- Missing credentials raise clear errors (not silent failures)
- Script imports resolve correctly
- argparse flags match documented interface

**Pre-merge gate:**
```bash
uv run ruff check tests/test_harvest_scripts.py
uv run pytest tests/test_harvest_scripts.py -v
uv run pytest tests/ -q                          # no regressions
```

**Merge criteria:**
- Every harvest script has at least 3 characterization tests
- Tests are behavioral (test what the script does, not how)
- All tests green

---

### PR-3: Extract HarvestRunner (#75)

**Branch:** `refactor/harvest-runner`
**Base:** `development` (after PR-2 merges)
**Blocked by:** PR-2 (characterization tests must exist first)
**Blocks:** Nothing

**Files created:**
- `src/datafactory_harvester/harvest_runner.py` -- shared runner
- `tests/test_harvest_runner.py` -- unit tests for runner

**Files modified:**
- `scripts/harvest_ucdp.py` -- delegate to HarvestRunner
- `scripts/harvest_acled.py` -- delegate to HarvestRunner
- `scripts/harvest_ghspop.py` -- delegate to HarvestRunner
- `scripts/harvest_ghsbuilts.py` -- delegate to HarvestRunner
- `scripts/harvest_priogrid.py` -- delegate to HarvestRunner
- `scripts/harvest_gaul.py` -- delegate to HarvestRunner
- `scripts/harvest_vdem.py` -- delegate to HarvestRunner
- `scripts/harvest_shdi.py` -- delegate to HarvestRunner
- `scripts/harvest_shapefile.py` -- delegate to HarvestRunner

**Pre-merge gate:**
```bash
uv run ruff check .
uv run pytest tests/test_harvest_runner.py -v
uv run pytest tests/test_harvest_scripts.py -v   # characterization tests still pass
uv run pytest tests/ -q                          # full suite
```

**Merge criteria:**
- All 9 harvest scripts use HarvestRunner
- PR-2 characterization tests still pass (no behavioral change)
- New unit tests cover: argparse, banner, timing, error propagation
- Each script is < 30 lines (thin delegate)
- Per-source argparse extensions work (e.g., ACLED `--year-range`)

---

### PR-4: Pipeline Runner Characterization Tests (#76)

**Branch:** `test/pipeline-runner-characterization`
**Base:** `development`
**Blocks:** PR-5 (PipelineRunner extraction)
**Parallel with:** PR-1, PR-2, PR-6

**Files created:**
- `tests/test_pipeline_scripts.py` -- characterization tests for all 4 pipeline runners

**Files modified:** None (test-only PR)

**What the tests must cover:**
- `--help` exits 0 for each runner
- `--skip-to` with valid step names accepted
- `--skip-to` with invalid step name raises error
- `--dry-run` flag accepted
- Step ordering is correct for each pipeline
- Missing credentials produce clear errors

**Pre-merge gate:**
```bash
uv run ruff check tests/test_pipeline_scripts.py
uv run pytest tests/test_pipeline_scripts.py -v
uv run pytest tests/ -q                          # no regressions
```

**Merge criteria:**
- Every pipeline runner has at least 4 characterization tests
- Tests cover `--skip-to` and `--dry-run` flags
- All tests green

---

### PR-5: Extract PipelineRunner (#77)

**Branch:** `refactor/pipeline-runner`
**Base:** `development` (after PR-4 merges)
**Blocked by:** PR-4 (characterization tests must exist first)
**Blocks:** Nothing

**Files created:**
- `src/datafactory_harvester/pipeline_runner.py` -- shared runner (or new top-level package)
- `tests/test_pipeline_runner.py` -- unit tests

**Files modified:**
- `scripts/run_ucdp_pipeline.py` -- delegate to PipelineRunner
- `scripts/run_acled_pipeline.py` -- delegate to PipelineRunner
- `scripts/run_ghspop_pipeline.py` -- delegate to PipelineRunner
- `scripts/run_ghsbuilts_pipeline.py` -- delegate to PipelineRunner
- `scripts/run_vdem_pipeline.py` -- delegate to PipelineRunner

**Pre-merge gate:**
```bash
uv run ruff check .
uv run pytest tests/test_pipeline_runner.py -v
uv run pytest tests/test_pipeline_scripts.py -v  # characterization tests still pass
uv run pytest tests/ -q                          # full suite
```

**Merge criteria:**
- All 4+ pipeline runners use PipelineRunner
- PR-4 characterization tests still pass
- `--skip-to`, `--stop-after`, `--dry-run` work identically
- Step definitions are declarative (list of name + callable tuples)
- Each script is < 40 lines

---

### PR-6: Viewpoint Scaffolding Extraction (#78)

**Branch:** `refactor/viewpoint-scaffolding`
**Base:** `development`
**Blocks:** Nothing
**Parallel with:** PR-1, PR-2, PR-4

**Files created:**
- `src/datafactory_viewpoint/builder_base.py` -- shared scaffolding (helpers or base class)
- `tests/test_viewpoint_scaffolding.py` -- tests for extracted scaffolding

**Files modified:**
- `src/datafactory_viewpoint/builders/ucdp_v1.py` -- use shared scaffolding
- `src/datafactory_viewpoint/builders/acled_v1.py` -- use shared scaffolding
- `src/datafactory_viewpoint/builders/ghspop_v1.py` -- use shared scaffolding
- `src/datafactory_viewpoint/builders/ghsbuilts_v1.py` -- use shared scaffolding
- `src/datafactory_viewpoint/builders/vdem_v1.py` -- use shared scaffolding

**Pre-merge gate:**
```bash
uv run ruff check .
uv run pytest tests/test_viewpoint_scaffolding.py -v
uv run pytest tests/test_viewpoint.py -v         # existing viewpoint tests
uv run pytest tests/ -q                          # full suite
```

**Merge criteria:**
- Config-or-shortcut + provenance + result construction extracted
- All 5 viewpoint builders use shared scaffolding
- Existing viewpoint tests pass (no behavioral change)
- V-Dem's ISO3 crosswalk pattern accommodated (not forced into spatial-join mold)
- Shared code is simpler than the duplication it replaces

**Design risk note:** This is the highest-risk extraction. If the abstraction
doesn't cleanly accommodate all 5 builders, defer and keep WET. The abstraction
must be simpler than the duplication.

---

### Sprint A Exit Gate

Before starting Sprint B or C, all Sprint A PRs must be merged and verified:

```bash
git checkout development
git pull origin development

# Full verification
uv run ruff check .
uv run pytest tests/ -q

# Confirm no regressions in existing functionality
uv run pytest tests/test_viewpoint.py -v
uv run pytest tests/test_harvest_scripts.py -v
uv run pytest tests/test_pipeline_scripts.py -v

# Line count sanity check: harvest scripts should be < 30 lines each
wc -l scripts/harvest_*.py

# Line count sanity check: pipeline runners should be < 40 lines each
wc -l scripts/run_*_pipeline.py
```

**Exit criteria:**
- All 6 PRs merged into `development`
- Full test suite green
- No lint errors
- Risk register C-164 updated with extraction status

---

## Sprint B: Bounded-Memory Compilation (1.5 working days)

### PR-7: Replace np.full() with open_memmap() (#79)

**Branch:** `refactor/memmap-compilation`
**Base:** `development` (after Sprint A exit gate)
**Blocks:** PR-8
**Parallel with:** Sprint C PRs (if Sprint A is done)

**Files modified:**
- `src/datafactory_compilation/pregridded_compilation.py` -- `np.full()` -> `open_memmap()`
- `src/datafactory_compilation/grid_compilation.py` -- `np.full()` -> `open_memmap()`
- `scripts/assemble_grid.py` -- assembly uses memmap
- `scripts/export_zarr.py` -- fix zarr materialization to not load full grid
- `tests/test_compilation.py` -- verify memmap behavior
- `tests/test_assemble.py` -- verify assembly with memmap

**Files created:**
- `docs/ADRs/037_bounded_memory_compilation.md` -- ADR for the approach

**Pre-merge gate:**
```bash
uv run ruff check .
uv run pytest tests/test_compilation.py -v
uv run pytest tests/test_assemble.py -v
uv run pytest tests/ -q
```

**Merge criteria:**
- `compile_pregridded()` and `compile_grid()` use `open_memmap()`
- Assembly step uses memmap (no full-grid allocation)
- Zarr export reads from memmap without materializing
- All compilation tests pass
- ADR-037 accepted
- Peak memory for a single-source compile < 2 GB (vs. ~9.7 GB before)

---

### PR-8: Pre-flight Resource Checks (#80)

**Branch:** `refactor/preflight-resource-checks`
**Base:** `development` (after PR-7 merges)
**Blocked by:** PR-7
**Blocks:** Nothing

**Files created:**
- `src/datafactory_compilation/preflight.py` -- resource estimation + checks
- `tests/test_preflight.py` -- unit tests

**Files modified:**
- `scripts/assemble_grid.py` -- call pre-flight before assembly
- Pipeline runner scripts -- call pre-flight before compilation step

**Pre-merge gate:**
```bash
uv run ruff check .
uv run pytest tests/test_preflight.py -v
uv run pytest tests/ -q
```

**Merge criteria:**
- Pre-flight estimates memory needed for given (T, H, W, F) shape
- Pre-flight warns if estimated memory > 80% of available RAM
- Pre-flight fails loud if estimated memory > available RAM
- Does not block legitimate operations on machines with sufficient RAM

---

### Sprint B Exit Gate

```bash
git checkout development
git pull origin development

uv run ruff check .
uv run pytest tests/ -q

# Memory verification (requires assembled grid)
# Peak RSS during assembly should be < 8 GB (was ~33 GB)
```

**Exit criteria:**
- PRs 7-8 merged
- ADR-037 accepted
- Peak memory for compilation demonstrably reduced
- C-223 updated or resolved

---

## Sprint C: Harvest Correctness (1.5 working days)

### PR-9: Cache Digest Verification (#81)

**Branch:** `fix/cache-digest-verification`
**Base:** `development` (after Sprint A exit gate)
**Blocks:** Nothing
**Parallel with:** PR-10

**Files modified:**
- `src/datafactory_harvester/sources/acled.py` -- add content digest check to cache logic
- `src/datafactory_harvester/sources/ghspop.py` -- add content digest check to cache logic
- `tests/test_acled_harvester.py` -- test cache hit with matching digest, cache miss with stale digest
- `tests/test_ghspop_harvester.py` -- test cache hit with matching digest, cache miss with stale digest

**Pre-merge gate:**
```bash
uv run ruff check .
uv run pytest tests/test_acled_harvester.py -v
uv run pytest tests/test_ghspop_harvester.py -v
uv run pytest tests/ -q
```

**Merge criteria:**
- Cache check verifies file content matches ledger digest (not just file existence)
- Stale cache (file exists but digest mismatch) triggers re-fetch
- New tests: cache hit (digest matches), cache miss (file exists, digest stale), cache miss (file missing)
- C-184 and C-185 resolved

---

### PR-10: Shapefile Outcome Vocabulary (#82)

**Branch:** `fix/shapefile-outcome-vocab`
**Base:** `development` (after Sprint A exit gate)
**Blocks:** Nothing
**Parallel with:** PR-9

**Files modified:**
- `src/datafactory_harvester/sources/priogrid_shapefile.py` -- `"changed": True/False` -> `"outcome": "success"/"unchanged"`
- `tests/test_priogrid_shapefile.py` -- test outcome vocabulary
- `docs/ADRs/032_*.md` -- update if needed to reflect standard vocabulary

**Pre-merge gate:**
```bash
uv run ruff check .
uv run pytest tests/test_priogrid_shapefile.py -v
uv run pytest tests/ -q
```

**Merge criteria:**
- Shapefile harvester uses `"outcome": "success"/"unchanged"/"failed"` (matching all other harvesters)
- All downstream consumers of shapefile result handle new vocabulary
- C-186 resolved

---

### Sprint C Exit Gate

```bash
git checkout development
git pull origin development

uv run ruff check .
uv run pytest tests/ -q
```

**Exit criteria:**
- PRs 9-10 merged
- C-184, C-185, C-186 resolved
- Full test suite green

---

## Execution Timeline

```
Day 1:  PR-1 (config validators)    -- merge same day
        PR-2 (harvest char tests)   -- start, merge day 1 or 2
        PR-4 (pipeline char tests)  -- start, merge day 1 or 2
        PR-6 (viewpoint scaffold)   -- start

Day 2:  PR-2 merge (if not done)
        PR-4 merge (if not done)
        PR-3 (HarvestRunner)        -- start after PR-2 merges
        PR-5 (PipelineRunner)       -- start after PR-4 merges
        PR-6 continue

Day 3:  PR-3 merge
        PR-5 merge
        PR-6 merge
        Sprint A exit gate

Day 4:  PR-7 (open_memmap)          -- start
        PR-9 (cache digest)         -- start in parallel
        PR-10 (shapefile vocab)     -- start in parallel

Day 5:  PR-7 merge
        PR-8 (pre-flight checks)    -- start after PR-7
        PR-9 merge
        PR-10 merge
        Sprint C exit gate

Day 6:  PR-8 merge
        Sprint B exit gate

Day 7:  Buffer / risk register updates / session report
```

---

## Risk Register Updates After Completion

| Entry | Expected State |
|-------|---------------|
| C-164 | Resolved -- patterns 1, 3, 7, 8 extracted |
| C-223 | Resolved -- bounded-memory compilation in place |
| C-184 | Resolved -- ACLED cache digest verified |
| C-185 | Resolved -- GHS-POP cache digest verified |
| C-186 | Resolved -- shapefile outcome vocabulary standardized |
| C-230 | Partially resolved -- script layer now has characterization tests |
| C-07  | Updated -- config validation centralized |

**Post-sprint register review:** Run `/review-rr triage` after all PRs merge to
verify header counts and cross-references are consistent.

---

## What Comes After

With C-164 extracted, adding the next data source (SHDI Sprint 2, WDI, or climate)
no longer means copying 5 patterns. New sources use `HarvestRunner`, `PipelineRunner`,
shared config validators, and viewpoint scaffolding out of the box.

**Immediate next steps (pick one):**
1. **SHDI Sprint 2** -- viewpoint builder + compilation + assembly integration
2. **WDI integration** -- new source, first consumer of all extracted patterns
3. **Verify script framework (C-155)** -- extract the ~5,466 lines of verify script duplication

Pattern #6 (provenance recording, 87 call sites) remains deferred under C-06 until
the 10th source triggers extraction.
