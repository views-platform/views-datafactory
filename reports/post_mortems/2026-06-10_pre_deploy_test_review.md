# Pre-Deploy Post-Mortem: Deep Test Review (v1.2.29)

**Date:** 2026-06-10
**Author:** Simon Polichinel von der Maase, Claude Code
**Scope:** Full green/beige/red test coverage audit — all ~108 test files, ~80 source modules, 31 CICs
**Branch:** chore/pre-deploy-drift-detection (from development)
**Method:** 5 parallel audit agents (Harvester, Consolidation+Viewpoint, Compilation+Assembly+Export+Query, Provenance+Infra, Falsification), each independently evaluating coverage from 5 expert perspectives
**Prerequisite:** tech-debt-cleanup (same session, completed before this review)

---

## What we did

Full-codebase test review as the second pre-deploy check before v1.2.29 deployment. The review classified every test as green (happy path), beige (edge/boundary), or red (adversarial/failure), mapped tests against all 31 CIC guarantee sections, and identified modules or functions with no test coverage at all.

**Baseline:** 1,713 passing tests, 0 failures, 8 skipped, 14 xfailed. Full suite in 8m45s.

**Coverage by expert domain:**

| Domain | Files audited | Modules audited | Gaps found |
|--------|--------------|-----------------|------------|
| Harvester (all 9 sources) | ~25 | ~15 | 5 |
| Consolidation + Viewpoint | ~20 | ~12 | 6 |
| Compilation + Assembly + Export + Query | ~25 | ~18 | 5 |
| Provenance + Infrastructure | ~20 | ~15 | 5 |
| Falsification + Cross-cutting | ~18 | ~20 | 2 |
| **Total** | **~108** | **~80** | **23** |

---

## What we found: the good

### 1. CIC guarantee coverage is 86%

Of the testable guarantees documented in 31 CICs (Section 3: Responsibilities and Guarantees), 86% have at least one test exercising them. This is strong for a project that wrote its first CIC less than four months ago. The CIC-test alignment sections themselves are the most useful prioritization tool — several CICs honestly declare "not yet written" in Section 10, which is more actionable than discovering the gap through external audit.

### 2. ACLED is the test quality benchmark

ACLED consolidation has the most complete test coverage of any module: schema drift tests, corrupted Parquet tests, cross-file dedup tests (including the flaky test we fixed earlier this session, C-266), and boundary condition tests for edge-year events. This is the standard that other sources should match. The fact that UCDP consolidation lacks comparable coverage (finding #10, merged into C-45) stands out precisely because ACLED sets the bar.

### 3. The synthetic test path carries significant weight

The synthetic end-to-end test path (C-029's partial mitigation, introduced in commit 0b9794d) exercises the full pipeline in ~3 seconds with gold-standard snapshots. Many of the Tier 4 gaps we registered are individually low-risk because this synthetic path provides integration-level coverage across all layers. Individual function-level tests for infrastructure utilities would add confidence but are not deployment-blocking.

### 4. No silent correctness bugs found

The review found no case where an existing test was wrong (testing the wrong thing, asserting the wrong value, or masking a bug). All 1,713 tests are correctly specified. The gaps are absences, not errors.

### 5. Provenance and skip modules are well-tested

The content-addressed skip module (`skip.py`, ADR-041) and the core provenance operations (`append_ledger_entry`, `compute_file_digest` at integration level) have strong green and beige coverage from the recent v1.2.29 work. The skip path in particular has adversarial tests (corrupted output, stale sentinel, key-set mismatch) that were written as part of the C-259/C-260/C-262 resolution.

---

## What we found: the gaps

### 1. The system of record has no crash-safety tests (C-267, Tier 2)

`event_store.py` implements the atomic write path for the consolidated store — temp file + `os.rename()` for crash-safe writes, `file_lock` for concurrent access. These are the most important mechanical properties of the system of record, and neither has a direct test. The atomic write pattern is correct (standard POSIX idiom), but a regression during refactoring would be undetectable. This is the only new Tier 2 finding.

### 2. Three Tier 3 gaps in foundational modules (C-268, C-269, C-270)

- **gaul_admin.py** (C-268): 7-feature source with spatial join and L1/L2 fallback. `_compute_cell_polygon_map` has 15 tests (C-246), but the higher-level pipeline functions — GAUL data loading, admin hierarchy parsing, fallback logic — have zero tests.
- **event_validation.py** (C-269): `validate_events()` and `compare_snapshots()` have zero direct tests. `compare_snapshots()` is the only mechanism to detect upstream data mutations between harvests. C-159 was demoted with the claim "both compare_snapshots and archive_snapshot are tested in their own modules" — the test review contradicts this for `compare_snapshots()`.
- **_rotate_ledger()** (C-270): Ledger rotation at 10MB has zero tests. A rotation bug could truncate the provenance audit trail. This function only triggers at scale (production ledgers approaching 10MB), so any bug would first manifest in production.

### 3. Eleven Tier 4 gaps across infrastructure (C-271 through C-281)

Individually low-risk, collectively a pattern: `compute_file_digest` (zero direct tests), `TemporalConfig` CIC failure modes (untested), `snapshot_storage.py` (no dedicated tests), `tagging.py` (1 test), `raster_io.py` (1 test), UCDP candidate/dot9 per-version fetch failures (untested), `check_disk_space` (untested), `ConsolidationResult`/`ViewpointResult` frozen-mutation (untested), `land_mask.py` (zero red tests), `skip.py` corrupted metadata (untested), and no SHDI CIC.

### 4. One false positive corrected

Finding #12 (_reconciliation.py untested in isolation) turned out to be a false positive — `test_hierarchical_reconciliation.py` exists with 6 tests (C-243 resolved). The audit agent missed the file because it wasn't in its assigned search scope. This is a good reminder that parallel audit agents can have coverage gaps at scope boundaries.

---

## Five structural insights

These observations cut across the individual findings and are the highest-value output of the review. They are not registrable risks — they describe the shape of the test architecture, not specific defects.

### Insight 1: Overall test health is strong

1,713 passing tests, 0 failures, 86% CIC guarantee coverage. The gaps are in infrastructure utilities and edge cases, not core data paths. The factory's test architecture is production-grade for a single-developer research project. This is not a codebase that needs a test-writing sprint — it needs targeted additions at specific high-leverage points.

### Insight 2: Test category imbalance is systemic

Across the codebase, green (happy path) tests dominate. Beige (boundary) coverage is thin but present where it matters most (ACLED dedup, compilation grid dimensions, temporal range boundaries). Red (adversarial) coverage exists mainly for ACLED consolidation and the skip module — modules that have been through incident-driven development. Most other modules have zero red tests.

This is not a bug-by-bug risk — it's a structural pattern. The test suite tells you that the system works correctly under expected conditions. It does not tell you how the system fails under unexpected conditions, except for the two modules that have been through postmortem-driven hardening.

**Implication for future work:** When writing tests for a new feature or fix, the highest-value addition is almost always a red test, not another green one. The green path is already well-covered. The question to ask is: "How could this break silently?"

### Insight 3: CIC test alignment sections are the best prioritization tool

Several CICs declare "not yet written" in their test alignment sections (Section 10). This self-documenting honesty is more actionable than external audit findings. When deciding where to write the next test, read the CIC first — if Section 10 says the guarantee is untested, that's the highest-leverage place to add coverage. The CIC already tells you what to test (Section 3: Guarantees) and how it should fail (Section 6: Failure Modes).

### Insight 4: The synthetic test path is an effective mitigation for many Tier 4 gaps

The synthetic end-to-end test path (3 seconds, gold-standard snapshots) exercises every layer of the pipeline with known-answer data. Many of the individual Tier 4 test coverage gaps (raster_io, tagging, snapshot_storage, etc.) are partially mitigated by this integration path. The synthetic path doesn't replace unit tests — it can't catch boundary conditions or adversarial inputs — but it does ensure that the happy path through every module is exercised in combination.

**Implication:** The next high-leverage testing investment is not "more unit tests for infrastructure" but "more failure scenarios in the synthetic path." Adding a corrupted-input variant of the synthetic dataset would exercise red paths across all layers simultaneously.

### Insight 5: The test architecture is production-shaped but lacks cross-layer adversarial testing

Each layer (harvester, consolidation, viewpoint, compilation, assembly, export) tests its own logic in isolation. This is correct and mirrors the graph architecture (ADR-012: layers are decoupled by the filesystem, not by imports). But no test exercises what happens when one layer produces subtly wrong output that the next layer silently accepts.

The provenance system is tested for correctness (digests match, ledger entries are written) but not for resilience (corrupted ledger, concurrent writes, rotation under load, truncated provenance.json). The test suite verifies that the system works; it does not verify that the system detects when it is broken.

This is the gap that the stale-zarr incident (2026-04-25) exploited and that the ACLED dedup incident (2026-06-07) reproduced: derived artifacts drifting from their source because no cross-layer check detected the inconsistency. The source-digest gates (ADR-041) are a structural fix for the specific assembly→export boundary, but the general pattern — "does layer N detect when layer N-1's output is wrong?" — is untested across most boundaries.

**This insight is tracked as GitHub issue #145 for dedicated investigation.**

---

## Risk register impact

| Metric | Before | After |
|--------|--------|-------|
| Total IDs | 266 | 281 |
| Open concerns | 57 | 72 |
| Tier 2 | 7 | 8 |
| Tier 3 | 11 | 14 |
| Tier 4 | 33 | 44 |

**15 new entries** (C-267 through C-281), **4 merged** into existing entries (C-45, C-29, C-264, C-230), **4 skipped** (1 false positive, 3 absorbed into other findings).

The tier distribution of new findings (1 Tier 2, 3 Tier 3, 11 Tier 4) is consistent with a mature codebase: the high-severity problems have already been found and fixed by prior audits. What remains is infrastructure hardening and edge-case coverage.

---

## What we'd do differently

### 1. Scope audit agents more carefully at boundaries

Finding #12 was a false positive because the agent assigned to "Compilation + Assembly + Export + Query" didn't search the consolidation test directory. When running parallel audit agents with domain-specific scopes, the test files for shared modules (like `_reconciliation.py`, which is in the compilation package but tested alongside consolidation) can fall through scope cracks. Next time: give each agent a list of test files, not a list of source directories.

### 2. Run the review before the tech-debt-cleanup, not after

The test review identified several gaps that the tech-debt-cleanup could have addressed in the same session (e.g., C-266 flaky test was found by tech-debt-cleanup but could have been flagged by test review first). Running the review first would produce a more targeted cleanup list.

### 3. Budget time for red test investment

This review identified that red tests are the highest-leverage gap. But writing red tests requires understanding failure modes, which requires reading CIC Section 6 — this is a different skill than writing green tests. A dedicated "red test sprint" focused on the top 5 CIC failure modes would produce more value than scattering test-writing across all 11 Tier 4 gaps.

---

## Deployment assessment

**The test review does not block deployment.** The 15 new register entries are all Tier 2-4 with future triggers — none require immediate action before v1.2.29. The single Tier 2 finding (C-267: event_store crash-safety) has a trigger of "refactoring the write path," which is not in scope for this deploy.

The factory's test health (1,713 tests, 0 failures, 86% CIC coverage) is the strongest it has been at any deployment gate.
