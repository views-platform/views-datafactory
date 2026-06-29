# Pre-Deployment Post-Mortem: v1.5.0 → v1.6.0

**Date:** 2026-06-29
**Author:** Simon Polichinel von der Maase, Claude Code
**Scope:** ADR-003 compliance (declared aggregation types), ADR-049 (spatial distribution of imprecise UCDP events), deploy readiness falsification, product plan update, issue hygiene
**Branch:** development (via 3 PRs: #299, #306, #307 + pending #308)
**Commits:** 18 non-merge + 3 merge (dd6009f..551af96), 2026-06-28 to 2026-06-29
**PRs:** #299 (ADR-003 declared aggregation types), #306 (ADR-049 spatial distribution), #307 (deploy readiness falsification), #308 (product plan v12, pending)
**Previous deployment post-mortem:** [v1.3.0](2026-06-15_deployment_v130.md)
**Previous pre-deploy post-mortem:** [v1.2.29 test review](2026-06-10_pre_deploy_test_review.md)

---

## What we did

Pre-deployment audit for v1.6.0. This release covers work from v1.4.0 and v1.5.0 (deployed but without postmortems) through the current development head. Three feature epics shipped since the last postmortem (v1.3.0), plus two pre-deploy epics and one housekeeping PR in the v1.6.0 window.

**Baseline at audit start (2026-06-28):**
- 2,308 tests collected, 3 expected failures (deploy gate tests), 18 xfails, 8 skips
- 50 ADRs, 32 CICs, 308 risk register IDs (277 resolved, 28 open, 8 open disagreements)
- 9 data sources, 79 assembled features, 9 packages under `src/datafactory_*`
- 18 open GitHub issues (all deferred work packages or investigations)

---

## What shipped since v1.3.0 (the last postmortem)

### v1.4.0 — V-Dem, data soundness, test hardening (deployed 2026-06-24)

| PRs | Scope |
|-----|-------|
| #216 | WDI integration roadmap |
| #218 | Coastal gap cell validation + africa_me_gaul region |
| #222 | views-frames adoption (FeatureFrame via views-frames v1.0.0) |
| #231 | Deploy readiness v1.4.0 — admin digest hardening + version bump |
| #233 | Documentation drift fix across 15 governance files |
| #241 | Pre-WDI test hardening — 33 tests + provenance locking fixes |
| #242, #243 | Deployment guide — merge-to-main step + bump/tag terminology |

**Key capabilities:** V-Dem (8 democracy indicators) as 8th data source. Coastal gap validation for 946 Africa+ME cells. FeatureFrame standardized via views-frames v1.0.0. 33 new tests for assembly, query, and provenance locking.

### v1.5.0 — Conservation, temporal alignment, scaling headroom (deployed 2026-06-27)

| PRs | Scope |
|-----|-------|
| #244-#248 | Status page fix, LICENSE, README, docs |
| #257 | Consumer bridge cleanup — removed lr_* rename |
| #265 | Count conservation hardening (NaN guard, float64 regression, intensive warning) |
| #273 | Assembly temporal alignment — ADR-047, first_valid provenance, pre-coverage warning |
| #287 | Scaling headroom + infrastructure test coverage (C-144, C-145) |

**Key capabilities:** Consumer bridge serves raw factory names (no rename). Assembly records `first_valid_*_month_id` in provenance. `load_dataset()` warns on pre-coverage temporal queries. Columnar extraction in grid compilation (C-144). Column-selective viewpoint reads (C-145).

### v1.6.0 window — ADR-003 compliance, ADR-049, deploy gates (2026-06-28 to 2026-06-29)

| PR | Scope | Files changed | Insertions |
|----|-------|--------------|------------|
| #299 | ADR-003 declared aggregation types | 14 | +1,030 |
| #306 | ADR-049 spatial distribution of imprecise UCDP events | 16 | +1,599 |
| #307 | Deploy readiness falsification tests | 5 | +232 |
| #308 | Product development plan v12 | 1 | +240 |

**Total since v1.5.0:** 40 files changed, 3,109 insertions, 149 deletions.

---

## What we found: the good

### 1. ADR-003 compliance eliminates prefix inference

The codebase had three live violations of ADR-003 ("Authority of Declarations Over Inference") where aggregation strategy was inferred from feature name prefixes (`_INTENSIVE_PREFIXES`, `_EXTENSIVE_PREFIXES`, `_SOURCE_PREFIXES`) rather than declared in configuration. PR #299 resolved this by:

- Adding `feature_agg_types` to `SourceEntry` in the source registry (ADR-048)
- Propagating declared types through assembly provenance into `features.json`
- Replacing all three prefix-inference call sites in adapters and conservation modules
- Deleting all prefix constant tuples

The fix is structurally complete: adding a new feature to a source now requires declaring its aggregation type in one place (the registry), and the declaration propagates through all downstream layers without inference. 121 new registry coherence tests verify the contract.

### 2. ADR-049 spatial distribution is the deepest viewpoint enhancement to date

Imprecise UCDP events (where_prec 4-6: admin-region or country level) were previously assigned only to their centroid cell, concentrating all fatalities in a single 0.5° cell when the event's real location spans an entire admin region or country. PR #306 distributes these events proportionally across all cells in the relevant polygon:

- **769-line dedicated test suite** (`test_spatial_distribution.py`) with green, beige, and red coverage
- **3 new source modules:** `spatial_weights.py`, `spatial_distribution.py`, viewpoint config extensions
- **2 provenance counters** added to the viewpoint builder: `n_spatially_distributed`, `n_excluded_where_prec`
- **CIC crosswalk path defaults fixed** (C-305: paths aligned with `refresh_pipeline.sh`)
- **ADR-049 §2 table corrected** (C-304: mechanism description matched to actual code)

### 3. Deploy readiness falsification caught 5 blockers before deployment

The falsification audit (`test_falsification_deploy_v160.py`, 155 lines) probed 5 deployment claims:

| Test | What it checks | Outcome at audit start |
|------|---------------|----------------------|
| F1 | Version bumped since last tag | **FAIL** — 1.5.0 already tagged |
| F2 | main is ancestor of development (ff-only possible) | **FAIL** — diverged |
| F6 | Completed sprint issues closed | **FAIL** — 68 open, 10 should be closed |
| F7 | Product plan not stale | **FAIL** — v11 references v1.2 |
| F8 | No stale release branches | **FAIL** — release/v1.5.0 exists |

Without the falsification gate, all 5 would have surfaced at deploy time as "why doesn't this work" surprises. Two have been resolved during this pre-deploy sprint (F6: 50 issues closed → 18 remaining; F7: product plan v12 written). Three remain as the deploy checklist (F1, F2, F8).

### 4. Risk register governance is current

The register was updated through all 3 epics (ADR-003, ADR-049, deploy readiness). 9 new entries registered and immediately resolved (C-299 through C-308). The register stands at 308 concern IDs with 277 resolved — a 90% resolution rate. No Tier 1 concerns open. The single Tier 2 (C-267: event_store crash-safety) has a future trigger (refactoring the write path) that is not in scope.

### 5. Test suite is the strongest it has been at any deployment gate

| Metric | v1.2.29 | v1.3.0 | v1.6.0 |
|--------|---------|--------|--------|
| Tests collected | 1,713 | ~1,900 | 2,308 |
| Failures | 0 | 0 | 3 (all expected deploy gate) |
| xfails | 14 | 17 | 18 |
| Skipped | 8 | 8 | 8 |
| ADRs | 41 | 43 | 50 |
| CICs | 31 | 32 | 32 |
| Risk register IDs | 281 | 290 | 308 |
| Resolution rate | 74% | 77% | 90% |

The 595 new tests since v1.3.0 come from: spatial distribution (769 lines), registry coherence (121 tests), pre-WDI test hardening (33 tests), conservation hardening, scaling headroom, temporal alignment, deploy readiness falsification, and infrastructure coverage.

---

## What we found: the gaps

### 1. Three deploy blockers remain (expected — the deploy checklist)

| Blocker | Resolution |
|---------|------------|
| F1: Version not bumped (1.5.0 already tagged) | Bump to 1.6.0 in pyproject.toml |
| F2: main/development divergence | Merge main into development to establish ancestry |
| F8: Stale release/v1.5.0 branch | Delete local + remote branch |

These are mechanical steps, not findings. The falsification tests exist to ensure they are not forgotten.

### 2. v1.3.0 postmortem "do differently" items still not addressed

Three items have been carried forward since v1.2.29 (4 deployment cycles):

| Item | Recommendation | Status |
|------|---------------|--------|
| Per-step duration logging | Add `date +%s` before/after each step in `refresh_pipeline.sh` | **Not done** — 4th carry-forward |
| Skip decision console logging | Print which digests matched and whether REBUILD or SKIP | **Not done** — 4th carry-forward |
| Deploy-readiness falsification as standard step | Add to deployment guide as pre-deploy checklist item | **Partially done** — falsification tests exist (PR #307) but not yet in deployment guide |

The first two have never been implemented across 4 deployments. They should either be implemented or explicitly deferred with a reason. Carrying forward indefinitely is a process smell.

### 3. No deployment-time postmortem was written for v1.4.0 or v1.5.0

Both versions were deployed (v1.4.0 on 2026-06-24, v1.5.0 on 2026-06-27) without post-deployment postmortems. The last postmortem is for v1.3.0 (2026-06-15). This breaks the convention established since v1.2.20. The rapid deploy cadence (3 versions in 12 days) explains the gap, but the convention exists because deployment surprises are only captured if someone writes them down while they're fresh.

### 4. Product plan was stale by 3 major versions

The product development plan (v11, dated 2026-05-08) referenced v1.2 as the current version and listed 821 tests, 29 ADRs, 6 sources. The actual state at audit time was v1.5.0, 2,308 tests, 50 ADRs, 9 sources. Product plan v12 (PR #308) corrects this.

This staleness was detected by the falsification test (F7). Without the gate, the plan would continue to diverge. The lesson: governance artifacts that don't have automated staleness detection drift silently.

### 5. 18 open GitHub issues remain

All 18 are deferred work packages (WP:), investigations (#145, #110, #114), or low-priority operational items (#124, #116, #97, #95, #217). None block deployment. The issue count dropped from 68 to 18 during this pre-deploy sprint (50 issues closed across 6 completed sprint epics).

---

## Risk register snapshot

| Metric | Value |
|--------|-------|
| Total concern IDs | 308 |
| Resolved | 277 (90%) |
| Open concerns | 28 |
| — Tier 1 (critical) | 0 |
| — Tier 2 (high) | 1 (C-267: event_store crash-safety) |
| — Tier 3 (medium) | 4 |
| — Tier 4 (low) | 17 |
| — Deferred by design | 6 |
| Open disagreements | 8 |
| Concerns resolved since v1.3.0 | 53 |

The register is in its healthiest state. Zero Tier 1 concerns. The single Tier 2 (C-267) has a trigger of "refactoring the write path," which is not planned for v1.6.0.

---

## v1.3.0 postmortem items — status

| Item | v1.3.0 recommendation | v1.6.0 status |
|------|------------------------|---------------|
| 1. Per-step duration logging | Add `Step N completed in Xs` | **Not done** — carried forward (4th time) |
| 2. Skip decision console logging | Print which digests matched | **Not done** — carried forward (4th time) |
| 3. Deploy-readiness falsification as standard step | Add to deployment guide | **Partial** — falsification tests exist in test suite, not yet in guide |

**Recommendation:** Either implement items 1 and 2 in the v1.6.0 deploy cycle or explicitly close them as "accepted — not worth the effort." Four carry-forwards is the limit before a recommendation becomes noise.

---

## Deployment readiness assessment

### Remaining mechanical steps

| Step | Effort | Risk |
|------|--------|------|
| 1. Merge PR #308 (product plan v12) | Trivial | None — docs only |
| 2. Bump version 1.5.0 → 1.6.0 in pyproject.toml | Trivial | None |
| 3. Merge main into development | 10 min | Low — resolves ff-only ancestry |
| 4. Delete release/v1.5.0 branch (local + remote) | Trivial | None |
| 5. Run v1.6.0 falsification tests | 5 min | Verification step |
| 6. Merge development → main (ff-only) | 5 min | Must succeed after step 3 |
| 7. Tag v1.6.0, deploy | 15 min | Standard procedure |

### What could go wrong during deployment

1. **Grid shape change triggers full assembly rebuild.** v1.5.0 grid has 79 features. If ADR-049 changes the viewpoint output (events now distributed across multiple cells instead of centroid-only), the UCDP compilation output will differ, triggering full assembly. Expected duration: ~7 hours on CPX32 (consistent with v1.3.0 experience).

2. **Spatial distribution increases cell-event count.** Events that were in 1 cell are now in N cells (proportionally weighted). Total fatality counts are conserved (ADR-040), but per-cell event counts will change. Downstream consumers should expect different spatial patterns for imprecise events.

3. **Feature metadata change in provenance.** `features.json` now includes `aggregation_type` for each feature (ADR-048). Consumers reading `features.json` for metadata will see new fields. The grid array itself is unchanged in format.

### Deployment blocking?

**No.** The 3 remaining deploy gate failures (F1, F2, F8) are mechanical steps that take under 30 minutes. The test suite has 2,308 tests with 0 unexpected failures. The risk register has 0 Tier 1 concerns. The product plan is current. Sprint issues are closed.

**The factory is ready to deploy** pending completion of steps 1-7 above.

---

## What we'd do differently for v1.7.0

1. **Write post-deployment postmortems immediately after deployment.** The v1.4.0 and v1.5.0 gap means deployment observations are lost. If the deploy cadence is too fast for full postmortems, write a 5-line deployment note (date, version, duration, obstacles, anomalies) and expand later.

2. **Resolve or close "do differently" items within 2 deployments.** Per-step duration logging and skip decision logging have been carried forward 4 times. Either implement them as the first task after v1.6.0 deployment, or explicitly close them with a note explaining why they aren't worth the effort.

3. **Run the deploy falsification tests as a standard pre-deploy step.** The tests exist (`test_falsification_deploy_v160.py`). The deployment guide should reference them as a gate. The next deploy should have a `test_falsification_deploy_v170.py` ready before the deploy cycle starts.

4. **Keep the product plan within 1 version of current.** The plan drifted from v1.2 to v1.5 without update. The F7 falsification test now catches this, but the discipline should be: update the plan as part of the deploy cycle, not as a catch-up task.

5. **Write the next deploy's falsification tests before starting work, not at the end.** The v1.6.0 falsification tests were written during the deploy sprint. Writing them before the sprint would have caught the issue hygiene problem (68 open issues) earlier.
