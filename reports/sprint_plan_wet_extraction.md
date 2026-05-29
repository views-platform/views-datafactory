# Sprint Plan: WET Extraction (C-164)

**Date:** 2026-05-29
**Status:** Draft — developing iteratively
**Branch:** TBD (from `development`)
**Register entries:** C-164 (trigger fired), C-07, C-155, C-195
**Work package:** WET-before-DRY refactor (register row 86)
**Estimated effort:** ~2-3 days (moderate extraction risk on patterns 3, 7)

---

## Problem Statement

C-164 tracks cross-layer WET debt across 5 pipeline sources (UCDP,
ACLED, GHS-POP, GHS-BUILT-S, V-Dem). The trigger has fired twice:
GHS-BUILT-S (2026-05-22) and V-Dem (2026-05-26) as the 4th and 5th
sources. With SHDI planned as the 6th source, every unextracted
pattern means copying ~100-250 lines per source.

The WET-before-DRY strategy (ADR: write 3 times before abstracting)
has succeeded — patterns are now concrete and clear from 5+ examples.
Time to extract.

---

## Pattern Inventory

C-164 tracks 8 numbered patterns. Status from the 2026-05-24
tech-debt investigation:

### Already Extracted (v1.2.21)

| # | Pattern | Lines | Status |
|---|---------|-------|--------|
| 2 | Consolidation `_tag_table()` | 34 | Extracted in v1.2.21 |
| 4 | Compilation output writer | 30 | Extracted in v1.2.21 |
| 5 | `_VIEWS_EPOCH_YEAR` constant | 2 | Extracted in v1.2.21 |
| 6 | Provenance recording | ~48 sites | Deferred — C-06 tracks |
| 9 | Raster I/O shared functions | 39 | Extracted in v1.2.21 |
| 10 | Temporal interpolation | — | Extracted in v1.2.21 |

### Remaining (This Sprint)

| # | Pattern | Identical lines | Files | Risk |
|---|---------|----------------|-------|------|
| 1 | Harvester config validators | 36 (12×3 UCDP) | 5 | Safe |
| 3 | Viewpoint builder scaffolding | 35 | 4 | Moderate |
| 7 | Pipeline runner scripts | 80-120 per file | 3 | Moderate |
| 8 | Harvest script wrappers | 150-250 per file | 7 | Moderate |

Plus: **Verify/visual audit scripts** (~5 files, ~5,466 lines,
~60% overlap) — identified during C-155 but not numbered in C-164.
These are the highest-volume duplication in the codebase.

---

## Pattern Details

### Pattern 1: Harvester Config Validators (Safe, ~1 hour)

**Files (5):**
- `src/datafactory_harvester/sources/ucdp_annual.py`
- `src/datafactory_harvester/sources/ucdp_candidate.py`
- `src/datafactory_harvester/sources/ucdp_dot9.py`
- `src/datafactory_harvester/sources/acled.py`
- `src/datafactory_harvester/sources/ghspop.py`

**Pattern:** Each config's `__post_init__` has identical validators:
```python
if self.timeout < 1:
    raise ValueError("timeout must be >= 1")
if self.page_size < 1:
    raise ValueError("page_size must be >= 1")
if self.max_retries < 1:
    raise ValueError("max_retries must be >= 1")
```

**Extraction approach:** Shared validator functions or a mixin. The
validators are pure (no side effects, no domain coupling).

**Risk:** Safe — validators have no behavioral coupling to the rest
of the harvester.

### Pattern 3: Viewpoint Builder Scaffolding (Moderate, ~3 hours)

**Files (4):**
- `src/datafactory_viewpoint/builders/acled_v1.py`
- `src/datafactory_viewpoint/builders/ghspop_v1.py`
- `src/datafactory_viewpoint/builders/ghsbuilts_v1.py`
- `src/datafactory_viewpoint/builders/ucdp_v1.py`

**Pattern:** Config-or-shortcut, file existence check, provenance
recording, ViewpointResult construction. ~35 identical lines per file.
Core logic differs (event filtering vs. spatial aggregation vs.
country-level expansion).

**Extraction approach:** Base builder class with template method, or
shared helper functions for the scaffolding steps. The template method
approach is cleaner but has higher design risk (getting the hook
points right for 4 different builder types).

**Risk:** Moderate — scaffolding is tightly coupled to config classes.
Wrong abstraction boundary = worse than WET.

**Note (from C-164):** "Highest design risk" in the pattern inventory.
V-Dem builder (`vdem_v1.py`) adds a 5th variant with a fundamentally
different crosswalk pattern (ISO3 → pgid). Any base class must
accommodate both spatial-join sources and country-level sources.

### Pattern 7: Pipeline Runner Scripts (Moderate, ~4 hours)

**Files (3):**
- `scripts/run_ucdp_pipeline.py` (~253 lines)
- `scripts/run_ghspop_pipeline.py` (~253 lines)
- `scripts/run_ghsbuilts_pipeline.py` (~280 lines)

**Combined:** ~846 lines with shared structure:
- argparse setup with `--skip-to`, `--stop-after` flags
- Sequential step execution with numbered log headers
- Timing per step
- Error handling with step-level recovery
- `--dry-run` support

**Extraction approach:** Shared runner with pluggable step definitions.
Each source provides a list of `(name, callable)` tuples; the runner
handles argparse, `--skip-to`, timing, and logging.

**Risk:** Moderate — step index handling and fallback validation vary
between runners. The V-Dem pipeline (`run_vdem_pipeline.py`, ~247
lines) would be a 4th consumer.

### Pattern 8: Harvest Script Wrappers (Moderate, ~2 hours)

**Files (7):**
- `scripts/harvest_ucdp.py`
- `scripts/harvest_acled.py`
- `scripts/harvest_ghspop.py`
- `scripts/harvest_ghsbuilts.py`
- `scripts/harvest_priogrid.py`
- `scripts/harvest_gaul.py`
- `scripts/harvest_candidates.py`

**Combined:** ~1,035 lines. Each is a thin wrapper:
```
parse args → build config → call harvester function → print summary
```

**Extraction approach:** Shared `harvest_main()` wrapper that takes
a config class and harvester function, handles argparse + timing +
banner boilerplate.

**Risk:** Moderate — argparse flags differ per source (e.g., ACLED
has `--year-range`, GHS-POP has `--epoch`). The shared wrapper needs
to support per-source argument extensions.

### Verify/Visual Audit Scripts (High Volume, ~4 hours)

**Files (~5):**
- `scripts/verify_ghspop.py`
- `scripts/verify_ghsbuilts.py`
- `scripts/verify_vdem.py`
- `scripts/verify_acled.py`
- `scripts/verify_ucdp.py`

**Combined:** ~5,466 lines with ~60% structural overlap. Shared
structure: load grid → compute statistics → generate plots → write
report. Domain-specific: feature selection, expected ranges, plot
types.

**Note (from C-164):** "Beyond code duplication, the verification
scripts also lack governance: no ADR, CIC, or standard defines what
a verification script must check, how plots are selected, or what
'PASS' means."

**Risk:** These are the largest duplication target but also the
highest-risk extraction. Each script has domain-specific checks that
resist generic abstraction. Consider extracting just the framework
(load, plot, report) and keeping domain checks per-source.

---

## Extraction Order (Recommended)

Based on ROI (lines saved per hour of effort) and risk:

1. **Pattern 1: Config validators** — Safe, trivial, 5 min each.
   Good warmup and establishes the extraction workflow.

2. **Pattern 8: Harvest wrappers** — 7 files, high structural
   similarity. Moderate effort but high line-count payoff.

3. **Pattern 7: Pipeline runners** — 3 files, moderate complexity.
   Second-highest payoff per file.

4. **Pattern 3: Viewpoint scaffolding** — Highest design risk.
   Do last so earlier extractions inform the approach.

5. **Verify scripts** — Highest volume but also highest risk.
   May be better as a separate sprint after patterns 1-4 are done.

---

## Task Breakdown

### Task 1: Config Validators (Pattern 1)
- [ ] Extract shared validators to `src/datafactory_harvester/validation.py`
  or add to existing config module
- [ ] Replace validators in 5 harvester configs
- [ ] Test: validators still raise on invalid input
- [ ] Test: valid configs still construct

### Task 2: Harvest Wrappers (Pattern 8)
- [ ] Design `harvest_main()` interface (config class + callable + optional extra args)
- [ ] Implement shared wrapper
- [ ] Convert 7 harvest scripts
- [ ] Test: each script still works with `--help` and basic invocation

### Task 3: Pipeline Runners (Pattern 7)
- [ ] Design shared runner interface (step list + argparse extensions)
- [ ] Implement shared runner with `--skip-to`, timing, logging
- [ ] Convert 3 pipeline scripts (UCDP, GHS-POP, GHS-BUILT-S)
- [ ] Test: `--skip-to`, `--stop-after`, `--dry-run` still work
- [ ] Consider converting V-Dem pipeline runner as 4th consumer

### Task 4: Viewpoint Scaffolding (Pattern 3)
- [ ] Analyze the 4 builder files for exact shared vs. different code
- [ ] Design extraction (base class vs. helper functions)
- [ ] Implement and convert 4 builders
- [ ] Test: each builder produces identical output to pre-extraction
- [ ] Consider V-Dem builder as 5th consumer (different crosswalk type)

### Task 5: Register Updates
- [ ] Update C-164 with extraction status
- [ ] Update C-07 (frozen dataclass pattern) if config validators change
- [ ] Update C-155 (visual audit framework) if verify scripts addressed
- [ ] Update C-195 (falsification test accumulation) if relevant
- [ ] Update header counts

---

## Design Principles

From the codebase's WET-before-DRY philosophy (C-44, now merged
into C-164):

1. **Extract only what's truly identical.** If two implementations
   differ in subtle ways, keep them separate. Three similar lines
   is better than a premature abstraction.

2. **The abstraction must be simpler than the duplication.** If the
   shared code needs more parameters than the original code had lines,
   the abstraction is wrong.

3. **Test before extracting.** Ensure each pattern has tests that
   verify behavior BEFORE refactoring, so extraction can be validated
   by running existing tests.

4. **One pattern per commit.** Each extraction is independently
   reviewable and revertable.

---

## Verification

```bash
uv run ruff check .
uv run pytest -q
# Pattern-specific checks:
uv run pytest tests/test_viewpoint.py -v     # viewpoint scaffolding
uv run pytest tests/test_harvest*.py -v      # harvest wrappers
```

---

## Open Questions

1. Should config validators move to `datafactory_harvester/validation.py`
   or to the existing config modules where the dataclasses live?
2. For pipeline runners: should the shared runner be a class or a
   function? (Function is simpler; class allows per-source hook methods)
3. For harvest wrappers: how to handle per-source argparse extensions?
   Subparsers? Callback for adding extra args?
4. Should verify scripts be part of this sprint or deferred to a
   separate sprint? (~4 hours additional, highest-risk extraction)
5. Does extracting pattern 3 (viewpoint scaffolding) require a new
   CIC for the base builder?
6. Should the V-Dem pipeline runner be converted in this sprint
   (4th consumer) or left for the SHDI sprint?

---

## Dependencies

- **Blocks:** SHDI integration (6th source would copy all patterns)
- **Blocked by:** Nothing
- **Related:** C-164 (primary tracking entry), C-07 (frozen dataclass),
  C-155 (visual audit framework), C-06 (provenance composability),
  Harvest correctness sprint (fixes C-184/C-185/C-186 in harvest layer)
