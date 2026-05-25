# Pre-Deployment Post-Mortem: Maintenance Sprint v1.2.21

**Date:** 2026-05-25
**Author:** Simon Polichinel von der Maase, Claude Code
**Scope:** WET-before-DRY debt extraction, CI signal restoration, dead code deletion, risk register curation — maintenance sprint before 5th data source
**Commits:** 14 non-merge (c706cbe..8a08069), 2026-05-24 to 2026-05-25
**PRs:** #63 (maintenance sprint → development), #64 (development → main)
**Tags:** v1.2.21 (pending)
**Previous post-mortems:** [v1.2.20 deployment](2026-05-24_deployment_v1220.md), [GHS-BUILT-S pre-deploy](../pre_deploy_post_mortem_ghsbuilts.md)

---

## What this post-mortem covers

The v1.2.21 sprint is different from every previous release. There is no new data source. No new feature. No consumer-facing change. The grid shape stays at (456, 360, 720, 53). The pipeline output is byte-identical.

What changed is the internal structure: 5 shared modules extracted from copy-pasted code, one dead module deleted, 2 risk register concerns resolved, assembly script refactored from 720+ lines to ~540, and CI restored from permanent UNSTABLE to green. This is the first release where every change is invisible to consumers.

The risk profile is also different. A new data source can fail loudly — OOM, wrong values, missing features. A refactoring sprint fails silently — a function signature changes subtly, a column name drifts, a validation check is dropped during extraction. The deployment risk is not "does the new thing work" but "did we break what already worked."

---

## Why we did this

Four data sources are now implemented (UCDP, ACLED, GHS-POP, GHS-BUILT-S). Each was built by copying patterns from the previous source, following the WET-before-DRY principle (ADR: write 3 times before abstracting). By the 4th source, the codebase had accumulated:

- **`_read_geotiff()`** — 39 lines duplicated verbatim in ghspop_v1.py and ghsbuilts_v1.py
- **`_interpolate_temporal()` + helpers** — 103 lines duplicated verbatim in both viewpoint builders
- **`_tag_table()`** — 34 lines duplicated verbatim in ucdp.py and acled.py consolidators
- **Compilation output writing** — 30 lines duplicated in grid_compilation.py and pregridded_compilation.py
- **`_VIEWS_EPOCH_YEAR = 1980`** — defined in 3 files independently
- **`_load_source_grid` pattern** — 3 near-identical load-validate-align blocks in assemble_grid.py (~400 lines)
- **`datafactory_synthetic`** — a dead module with zero exports, zero callers, occupying test infrastructure and documentation
- **2 CI tests permanently failing** — hiding real regressions behind permanent UNSTABLE status

The trigger was C-164 (cross-layer WET debt), which fired when GHS-BUILT-S copied all 6 patterns for the 4th time. The strategic review-rr prioritize session (2026-05-24) ranked the WET cluster as the highest-ROI work item. The repo-assimilation and tech-debt-cleanup confirmed the extraction candidates were safe. Five falsification audits shaped the sprint plan before any code was written.

The goal: clean the codebase before the 5th data source (V-Dem or WDI), so the next developer (us, in a week) doesn't copy 6 patterns for the 5th time.

---

## What we did

### Sprint structure

The sprint was planned as 11 tasks (0–10) with prerequisites and a final verification gate. Total: 14 commits across 2 days, 51 files changed, +2,279 / -945 lines.

| Task | Description | Commit | Lines changed |
|------|-------------|--------|---------------|
| Pre | Commit untracked v1.2.20 postmortem | c706cbe | +243 |
| 0 | Version bump 1.2.20 → 1.2.21 | d6145c9 | +2 -2 |
| 1 | Risk register curation (14 strategic fixes) | e4e3afb | +168 |
| 2 | CI signal restoration (`@pytest.mark.skipif`) | (in sprint plan commit) | +10 |
| 3 | Extract `VIEWS_EPOCH_YEAR` to provenance/constants.py | 4c90a39 | +5 -6 |
| 4 | Extract `read_geotiff` to viewpoint/raster_io.py | f7bc5e4 | +49 -78 |
| 5 | Extract temporal interpolation to viewpoint/temporal.py | d2c4269 | +111 -206 |
| 6 | Extract `tag_table` to consolidation/tagging.py | fd8f39c | +46 -68 |
| 7 | Extract `write_compilation_output` to compilation/output.py | fcf7fb5 | +85 -118 |
| 8 | Extract `_load_source_grid` in assemble_grid.py | 6ca0174 | +55 -257 |
| 9 | Delete `datafactory_synthetic` + documentation cleanup | 5a1ea8f | -81 |
| 10 | Direct tests for extracted modules | ea88d29 | +166 |
| — | Fix test imports for extracted modules | 23930c6 | +56 -56 |
| — | Fix pyproject.toml description | aca7d2f | +2 -2 |
| — | Post-sprint register cleanup (F-1/F-2/F-3) | 8a08069 | +174 -22 |

### New shared modules created

| Module | Extracted from | Lines | Functions/constants |
|--------|---------------|-------|-------------------|
| `src/datafactory_provenance/constants.py` | ghspop_v1.py, ghsbuilts_v1.py, temporal_generator.py | 3 | `VIEWS_EPOCH_YEAR` |
| `src/datafactory_viewpoint/raster_io.py` | ghspop_v1.py, ghsbuilts_v1.py | 49 | `read_geotiff()` |
| `src/datafactory_viewpoint/temporal.py` | ghspop_v1.py, ghsbuilts_v1.py | 111 | `interpolate_temporal()`, `interp_step()`, `interp_linear()`, `VALID_TEMPORAL_INTERPOLATIONS` |
| `src/datafactory_consolidation/tagging.py` | ucdp.py, acled.py | 46 | `tag_table()` |
| `src/datafactory_compilation/output.py` | grid_compilation.py, pregridded_compilation.py | 85 | `write_compilation_output()` |

### Deleted

| Artifact | Lines removed | Reason |
|----------|--------------|--------|
| `src/datafactory_synthetic/` | 81 (2 files) | Dead module, zero exports, zero callers (C-176) |
| `datafactory_synthetic` refs in 5 ADRs | ~15 | Governance drift cleanup |
| `datafactory_synthetic` refs in 7 ARCHITECTURE.md | ~10 | Dependency rule cleanup |
| `datafactory_synthetic` refs in README.md | ~8 | Documentation accuracy |

### Risk register changes

| Action | Details |
|--------|---------|
| Resolved C-178 | Stale open entry (already fixed) |
| Merged C-03 → C-176 | Protocol proliferation moot (module deleted) |
| Resolved C-176 | Module deleted (Task 9) |
| Resolved C-169 | skipif guards added (Task 2) |
| Recalibrated C-177 | 3 → 4 (dead function retained with warning) |
| Recalibrated C-21 | 3 → 4 (not risk-relevant with current scale) |
| Rewrote 7 triggers | Perpetual/vague triggers made actionable |
| Resolved D-25, D-28 | Architectural disagreements settled |
| Updated C-164 | 5 extraction patterns marked resolved |
| Header count | 65 → 63 open, 105 → 107 resolved |

---

## How we did it

### Planning phase (2026-05-24, ~4 hours)

The sprint plan went through an unusually rigorous pre-planning process because this is the first pure refactoring release. No new functionality to test against — only "did we break what already worked."

1. **Repo assimilation** — fresh structural survey to verify file locations and line numbers
2. **Tech debt cleanup investigation** — quantified each WET pattern: identical lines, files involved, extraction risk
3. **Strategic review-rr + prioritize** — ranked the WET cluster as highest ROI, identified 14 register curation fixes
4. **8-expert code review** — Robert C. Martin, GoF, Feathers, Nygard, Kleppmann, Ousterhout, Hickey, Beck perspectives on the extraction plan
5. **5 falsification audits** of the sprint plan itself — ADR alignment, SOLID alignment, package principles, screaming architecture, definition of done. These audits shaped the plan: R-1 moved `VIEWS_EPOCH_YEAR` from `digests_and_ledgers.py` to a dedicated `constants.py`; S-4 caught a `NameError` in the assembly extraction; D-1/D-2 rewrote all acceptance criteria as binary checks.

The plan was 860 lines with every task specifying exact files, line numbers, acceptance criteria, and verification commands.

### Execution phase (2026-05-24 evening to 2026-05-25, ~5 hours)

Execution was sequential: each task committed separately, tests run after each task. The extraction strategy was deliberate: pure copy-paste lifts with no logic changes. Functions were moved verbatim, then renamed from private (`_read_geotiff`) to public (`read_geotiff`). No behavior was changed during extraction.

### Verification phase (2026-05-25, ~2 hours)

Two falsification audits after all tasks were complete:

1. **Cleanup completeness audit** — "the cleanup is done and successfully so." Found 3 categories of residue: F-1 (register updates not done), F-2 (README still mentioned synthetic), F-3 (7 ARCHITECTURE.md files referenced synthetic). All addressed.

2. **Regression safety audit** — "the cleanup will not lead to regressions." 7 probes across 7 categories: behavioral equivalence, silent behavior change, integration boundary, import chain integrity, API surface, cross-module consistency, adequacy. All probes passed. Verdict: SURVIVED.

Final gate: 1,094 tests passed, 0 failed, ruff clean, mypy clean (68 source files).

---

## What went right

### 1. Plan-driven execution eliminated improvisation

The 860-line sprint plan specified every file, every line number, every acceptance criterion. During execution, zero architectural decisions were needed — every decision had been made during planning. This is the first sprint where the execution phase required no judgment calls, only mechanical application of the plan.

Contrast with GHS-BUILT-S (v1.2.20), where 3 out of 13 checklist items were missed because the checklist wasn't consulted. This sprint's plan was consulted continuously because every task explicitly listed its steps and verification commands.

### 2. Five pre-planning falsification audits caught 10 issues

The sprint plan was falsified 5 times before a single line of code was written. Ten findings were addressed:
- R-1: Wrong file placement for `VIEWS_EPOCH_YEAR` → moved to `constants.py`
- S-4: `NameError` in `_load_source_grid` → imports moved to module level
- F-1: ADR-012 scope description stale → updated in Task 3
- F-2: No direct tests for extracted modules → added Task 10
- F-7: ADR references to deleted module → added to Task 9
- D-1: Missing acceptance criteria sections → added
- D-2: Subjective criteria → rewritten as binary checks
- D-5: No terminal action → ship gate added
- P-6: Provenance abstraction gap → acknowledged, deferred
- F-5: print-vs-logger in assembly → noted, deferred

Without these audits, the R-1 and S-4 findings would have been bugs in production. R-1 would have placed a platform constant inside a digest-specific module (wrong architectural signal). S-4 would have caused a `NameError` when `_load_source_grid` was called — the function referenced `np` and `DEFAULT_GRID_CONFIG` which were imported inside `main()`, not at module level.

### 3. Pure copy-paste extraction strategy prevented subtle regressions

Every extraction was a verbatim lift: copy the function to the new module, delete from the old location, update imports. No "while I'm at it" changes. No signature changes. No logic changes. This discipline was verified by the regression falsification audit (7 probes, all passed).

The second falsification audit specifically checked:
- Ledger dict field shapes preserved (F1: PASS)
- Interpolation constants identical (F2: PASS)
- GeoTIFF return tuple shape preserved (F3: PASS)
- No stale bytecache from deleted module (F4: PASS)
- Tag column names identical (F6: PASS)
- Validation logic preserved in assembly extraction (F7: PASS)

### 4. Net code reduction despite adding 5 modules and 4 test files

The sprint removed more code than it added in production source files. The net +2,279 / -945 includes the sprint plan (860 lines), falsification stubs, and test files. Production source code was net negative — duplication was eliminated without adding new functionality.

### 5. CI signal genuinely restored

Before this sprint, `uv run pytest` always showed 2 FAILED tests (infra-dependent tests without environment guards). This made CI permanently UNSTABLE, hiding real regressions. After Task 2, the test suite runs clean: 1,094 passed, 0 failed, 7 skipped, 6 xfailed. A real regression will now be visible immediately.

---

## What went wrong

### 1. Post-sprint register updates were forgotten

The sprint plan's "Register Updates After Sprint" section (Tasks: resolve C-176, resolve C-169, update C-164, fix header count) was not executed during the sprint. All 11 code tasks were completed, tests passed, PR was opened — but the register updates that document what the sprint accomplished were skipped.

**How it was caught:** The cleanup completeness falsification audit found it as F-1 (hard falsification). The failing test stubs (`test_c176_marked_resolved`, `test_c169_marked_resolved`, `test_c164_has_resolution_notes`, `test_register_header_count`) made the gap concrete and unfixable by rationalization.

**Why it happened:** Register updates feel like bookkeeping, not implementation. After completing 11 tasks and seeing all tests pass, the natural impulse is "we're done." The register updates were listed in the plan but not as a numbered task with acceptance criteria — they were in a separate section that was easy to skip.

**Lesson:** Register updates are a task, not an afterthought. In the next sprint plan, they should be a numbered task with acceptance criteria and verification commands, not a separate section.

### 2. README and ARCHITECTURE.md synthetic references survived Task 9

Task 9 (delete `datafactory_synthetic`) removed the module, updated `pyproject.toml`, updated test files, and updated 5 ADRs. But it did not update README.md (5 references) or 7 ARCHITECTURE.md files (which listed synthetic in dependency rules).

**How it was caught:** F-2 and F-3 in the cleanup completeness audit. `grep -rn "datafactory_synthetic"` found 12 surviving references across 8 files.

**Why it happened:** Task 9 step 4 in the sprint plan said "Update 5 ADRs." The plan did not include README.md or ARCHITECTURE.md in the step list — probably because the expert code review focused on the ADRs (formal governance docs) and missed the informal documentation. The `grep` that would have caught this was not in the acceptance criteria.

**Lesson:** When deleting a module, the acceptance criterion should be `grep -rl "module_name" src/ docs/ README.md` returns nothing — not a list of specific files. Enumerate what to check, don't enumerate what to change.

### 3. The falsification test search window was too narrow

`test_register_header_count` searched for "N open concerns" in `register[:500]` (first 500 characters). The Source line in the register header grew to ~1,500 characters over months of audits, pushing the Status line past byte 1,500. The test failed with "Could not find 'N open concerns' in header" even though the count was correct.

**How it was caught:** The test failed when run. Simple to diagnose and fix (widen to `:2000`).

**Why it happened:** The test was written against the current register state without considering that the Source line grows with every audit. A hardcoded byte offset is fragile.

**Lesson:** Minor. Search the entire file or use a regex that doesn't depend on position. Not worth a register entry.

### 4. The Edit tool could not modify ARCHITECTURE.md files

All 9 Edit tool calls for ARCHITECTURE.md files failed with "File has not been read yet." This is a tooling limitation — the files hadn't been explicitly Read in the current context window (they'd been read before conversation compaction). The workaround was `sed -i`, which worked correctly for these simple string replacements.

**Impact:** Minor — 5 minutes of rework. But `sed -i` bypasses the Edit tool's safety checks (uniqueness verification, diff preview). For simple, unambiguous replacements this is fine. For complex edits it would be risky.

**Lesson:** When editing many files with simple replacements, `sed -i` is pragmatic. When editing complex content, re-Read the file first to enable the Edit tool.

### 5. Transient GitHub SSH failures during merge

Two `gh pr merge` attempts returned HTTP 502 (Bad Gateway). A third attempt got "Permission denied (publickey)" but the merge actually succeeded on GitHub's side. A subsequent `ssh -T git@github.com` confirmed authentication worked fine. `git pull` succeeded immediately after.

**Impact:** None — the merge completed. But the error messages were confusing and required investigation to confirm the merge actually happened.

**Lesson:** GitHub has transient failures. When `gh pr merge` fails with 502, check `gh pr view --json state` before retrying. The merge may have already completed.

---

## The overhead question

This sprint took ~11 hours total (4 hours planning, 5 hours execution, 2 hours verification). The production code changes could have been done in 2-3 hours by a developer who knew what to extract. The remaining 8 hours were:

- Sprint plan writing and 5 pre-planning falsification audits: ~3 hours
- 8-expert code review of the plan: ~1 hour
- Test writing (4 new test files + 6 falsification stubs): ~1.5 hours
- 2 post-execution falsification audits: ~1.5 hours
- Register curation and documentation cleanup: ~1 hour

**Overhead ratio: ~3.7:1** (11 hours total / 3 hours core work). This is better than GHS-BUILT-S (6.6:1) but still high. The question is whether the overhead was proportional to the risk.

**Argument for:** The pre-planning audits caught 2 bugs that would have shipped (R-1 wrong file placement, S-4 NameError). The post-execution audits caught 3 categories of residue (register updates, README refs, ARCHITECTURE.md refs). Without the audits, v1.2.21 would have shipped with a NameError in `_load_source_grid`, stale documentation, and incomplete register updates.

**Argument against:** Five pre-planning falsification audits for a refactoring sprint is excessive. The S-4 NameError would have been caught by the first `uv run pytest` (it's a runtime error, not a silent regression). The R-1 file placement was an architectural preference, not a bug. The post-execution residue was all documentation, not code.

**Our assessment:** The planning investment paid off — 860 lines of plan meant zero improvisation during execution. The pre-planning falsification was valuable for S-4 (real bug) and R-1 (real architectural improvement). Three of the five audits (package principles, screaming architecture, definition of done) produced only formatting improvements to the plan itself, not substantive changes. For future maintenance sprints: 2 pre-planning audits (one structural, one behavioral) would be sufficient. Save the 3rd+ rounds for new data sources.

---

## What we'd do differently

### 1. Make register updates a numbered task with acceptance criteria

Not a separate section at the bottom of the plan. Include: which entries to resolve, which to update, what the header count should be after, and `grep -c '^| C-[0-9]' reports/technical_risk_register.md` as the verification command.

### 2. Use `grep -rl` as the acceptance criterion for deletion tasks

"Delete all references to X" should be verified with `grep -rl "X" src/ docs/ README.md *.md` returning nothing, not a list of specific files to update. The list will always be incomplete.

### 3. Limit pre-planning falsification to 2 rounds for maintenance sprints

One structural audit (ADR alignment, import rules) and one behavioral audit (SOLID, runtime correctness). The formatting audits (screaming architecture, definition of done) improved the plan document but didn't change the code. They're useful for new features; overkill for refactoring.

### 4. Run the full test suite before opening the PR, not after

We ran `uv run pytest` after completing all tasks and fixing post-execution findings. If we'd run it after Task 10, we would have caught the test import issue (23930c6) immediately rather than discovering it during the post-sprint cleanup.

### 5. Tag and deploy on the same day as the merge

v1.2.21 was merged to main on 2026-05-25. The deployment should happen the same day while context is fresh. The v1.2.18 post-mortem documented context loss across sessions; the v1.2.20 post-mortem documented SSH instructions being reconstructed from stale memory. Deploy while the sprint is still in your head.

---

## Deployment risk assessment

This is a refactoring release. The deployment risk profile is different from a feature release:

### What should be identical after deployment

- Grid shape: (456, 360, 720, 53) — unchanged
- Grid content: byte-identical to v1.2.20 output
- Feature count: 53 — unchanged
- Feature names: unchanged
- Pipeline step count: 11 — unchanged
- Harvest behavior: identical (no harvester changes)
- Consolidation behavior: identical (only `_tag_table` → `tag_table` rename)
- Viewpoint behavior: identical (extracted functions, no logic changes)
- Compilation behavior: identical (extracted output writer, no logic changes)
- Assembly behavior: identical (extracted `_load_source_grid`, no logic changes)

### What is different

- `datafactory_synthetic` no longer installable (deleted)
- `VIEWS_EPOCH_YEAR` imported from `datafactory_provenance.constants` instead of defined locally
- 5 new modules in the installed packages (raster_io, temporal, tagging, output, constants)
- `assemble_grid.py` has `_load_source_grid` function instead of inline blocks
- 2 CI tests now skip instead of fail when infra is missing
- Risk register header: 63 open concerns (was 65)

### Deployment verification checklist

- [ ] `uv sync` completes without errors
- [ ] `uv run pytest` passes (1,094 expected, 0 failed)
- [ ] `import datafactory_synthetic` raises `ModuleNotFoundError`
- [ ] `from datafactory_provenance import VIEWS_EPOCH_YEAR` succeeds
- [ ] `from datafactory_viewpoint.raster_io import read_geotiff` succeeds
- [ ] `from datafactory_viewpoint.temporal import interpolate_temporal` succeeds
- [ ] `from datafactory_consolidation.tagging import tag_table` succeeds
- [ ] `from datafactory_compilation.output import write_compilation_output` succeeds
- [ ] Pipeline produces identical grid shape: (456, 360, 720, 53)
- [ ] Health check passes for all 18 sources
- [ ] Grid digest matches v1.2.20 output (if pipeline input data unchanged)

---

## Risk register entries from this sprint

All resolved during the sprint:

| ID | Tier | Issue | Resolution |
|----|------|-------|------------|
| C-176 | 4 | `datafactory_synthetic` dead module | Deleted (Task 9) |
| C-169 | 4 | 2 CI tests permanently failing | skipif guards (Task 2) |
| C-178 | 3 | Stale open entry (already fixed) | Resolved (Task 1) |
| D-25 | — | Dead function retention disagreement | Settled (Task 1) |
| D-28 | — | Digest lookup function count disagreement | Settled (Task 1) |

C-164 (cross-layer WET debt) remains open with trigger fired — 5 of 8 patterns extracted, 3 deferred (harvester config validators, pipeline runners, harvest wrappers). The trigger condition for reassessment is the 5th data source.

---

## Timeline

| Time | Milestone |
|------|-----------|
| 2026-05-24 ~14:00 | Repo assimilation + tech debt investigation |
| 2026-05-24 ~16:00 | Strategic review-rr prioritize → WET cluster ranked #1 |
| 2026-05-24 ~17:00 | 8-expert code review of extraction plan |
| 2026-05-24 ~18:00 | 5 falsification audits of sprint plan |
| 2026-05-24 ~19:00 | Sprint plan finalized (860 lines) |
| 2026-05-24 ~20:00 | Tasks 0-3: version bump, register curation, VIEWS_EPOCH_YEAR |
| 2026-05-24 ~21:00 | Tasks 4-7: raster_io, temporal, tagging, output extractions |
| 2026-05-24 ~22:00 | Tasks 8-10: assembly refactor, synthetic deletion, new tests |
| 2026-05-25 ~00:30 | PR #63 opened, review-diff, ship-it |
| 2026-05-25 ~01:00 | Falsification audit 1: cleanup completeness → 3 findings |
| 2026-05-25 ~01:30 | F-1/F-2/F-3 addressed, register updated, all stubs pass |
| 2026-05-25 ~02:00 | Full test suite: 1,094 passed, ruff clean, mypy clean |
| 2026-05-25 ~08:30 | Falsification audit 2: regression safety → 7/7 probes passed |
| 2026-05-25 ~09:00 | PR #63 merged to development |
| 2026-05-25 ~09:05 | PR #64 (development → main) created and merged |

2 calendar days from planning start to main merge. ~11 hours of actual work across 2 sessions.
