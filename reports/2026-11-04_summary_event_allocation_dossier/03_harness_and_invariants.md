# 03 — Harness and invariants

**Date:** 2026-11-04 · **Audit basis:** views-datafactory @ `a45d485`
**Verdict: the standing harness is largely in place; the program-specific harness does not exist at
all.** The gap is evaluation, not safety.

---

## A. Invariant taxonomy

### A1. Hard invariants — never break (an experiment violating one is invalid, not merely worse)

| Invariant | Source | How it is enforced today |
|---|---|---|
| **Count conservation**: `placed + excluded = input`, every exclusion declared and quantified | ADR-040 Invariant 1 | provenance-ledger counters (`n_excluded_where_prec`, `n_passthrough_where_prec`, `n_skipped_spatial/temporal`) |
| **Hierarchical reconciliation**: admin levels in a family produce identical totals | ADR-040 Invariant 2 | `_conservation.py` in the adapters layer |
| **Extensive vs intensive**: only extensive quantities are summed | ADR-040, ADR-048 | `feature_agg_types` declared on the export |
| **Fail loud, never silently clamp** | ADR-011 | throughout; exit codes and ledger `outcome: "failed"` |
| **Byte-identical regeneration** of the consumer contract fixture | ADR-050 | `test_regeneration_is_byte_identical`, `test_fixture_digest_matches_contract` |
| **`production_parity` stays byte-identical while any new path is off** | this program's own commitment | **gap — no test asserts it; see C3** |
| Full suite green; `enforce_admins: true` on protected branches | repo policy | branch protection + CI (`lint`/`typecheck`/`test`, plus `docs`/`test-py313`/`import-enforcement` on main) |

⚠️ **One hard invariant appears already violated.** `ceil_split` assigns `ceil(best/span)` per month,
so mass over rows exceeds mass over events by **31,672 (0.91%)**. ADR-040 Invariant 1 requires
`aggregate(D_out) = aggregate(D_placed)`. This is pre-existing, affects only the 181 spread events,
and is **documented in `ceil_split`'s own docstring** — but it is not declared in the ledger as an
exclusion/inflation, which is what the invariant demands. **Routed to `register-risk`; not fixed
here, and not this program's to fix inside an experiment.**

### A2. Deliberately changed by this program (behind a flag)

State plainly so reviewers do not defend them:

1. **That an annual-source event is assigned wholly to its `date_end` month.** We intend to replace
   this for `date_prec ≥ 4` events spanning >1 month, in a non-parity profile only.
2. **That a `where_prec ≥ 4` event is assigned wholly to its centroid cell.** ADR-049 already
   decided to replace this; we intend to make that decision live.
3. **That the export carries no per-cell-month precision provenance.** We intend to add it.

**`production_parity` itself is not changed.** All three changes land in a separate profile. What
changes is which profile the pipeline invokes — a one-line, reversible, auditable decision.

### A3. Respect while changing — not targeted, breakable in passing

- **Survivorship (`dot9_wins`, `filter_stale_versions`)** — allocation runs after survivorship;
  reordering would silently change which event versions are allocated.
- **`exclude_where_prec=(4, 6)`** — interacts with any spatial strategy: an event dropped by the
  filter can never be distributed. Filter-then-distribute ordering is load-bearing.
- **Temporal-then-spatial ordering** (ADR-049 §4) with independent conservation at each stage.
- **ADR-041 content-addressed skip** — changing viewpoint output changes digests and will
  invalidate skip caches; expect a full recompute and do not mistake it for a fault.
- **ADR-052 extrapolation gate** and source coverage bounds.
- **The `annual` source-type tag itself** — `source_distribution_map` keys on it.

---

## B. The standing harness — what the audit found (reuse, do not reinvent)

| Mechanism | Status | Evidence |
|---|---|---|
| **Extension seam (OCP)** | ✅ **strong** | `datafactory_provenance.registry.Registry` with `@_registry.decorator("name")`. `temporal_distribution.py`'s docstring states the contract: *"no changes to the builder (OCP)."* **A new allocation strategy is registered, not patched in.** |
| **Default-off flags** | ✅ via profiles | ADR-016 viewpoint profiles; `_register(...)` + `load_profile(name, **overrides)`. A new profile is inert until named, and `build_viewpoint.py` defaults to `--profile production_parity`. |
| **Parity / regression gates** | ✅ **strong** | 2,433 passing tests; ADR-050 byte-identical fixture + digest contract; `test_contract_conformance.py`; `test_docs_citations.py`; 20+ falsification suites. |
| **Reproducibility** | ✅ | content digests (`_harvest_digest`), provenance ledgers, `LEDGER_VERSION`, ADR-041 content-addressed skip. |
| **Fast, cheap readout** | ✅ | synthetic per-source datasets with gold-standard snapshots; `scripts/generate_synthetic_data.py` + `tests/test_synthetic_pipeline.py` (25 tests). Sub-minute, known-answer. |
| **Negative-result discipline** | ✅ **strong** | `reports/post_mortems/` (16 entries); `reports/technical_risk_register.md` (365 IDs); `reports/register_changelog.md`; the `reports/investigation_*/` convention with pre-analysis plans. |
| **Run discipline** | ✅ | one-heavy-job-at-a-time norm; background + completion-notify; timestamped artifacts; healthchecks.io dead-man heartbeat; C-345 (exit 137 is OOM, not green). |
| **Evaluation comparability** | ❌ **absent for this program** | There is **no locked baseline, no metric protocol and no ground truth for allocation quality.** Nothing in the repo evaluates whether an allocation is *good* — only whether it is *conservative* and *reproducible*. **This is the gap.** |
| Hardware/runtime gates | ~ n/a | CPU-only pipeline; the relevant gate is memory (C-345), which exists. |

**Honest summary: roughly 85% of the standing harness already exists.** This repo is unusually
well-instrumented for safety. What it has never needed — because allocation was never treated as a
choice — is an instrument for allocation *quality*.

---

## C. New harness this program must build first

### C1. The coarsen-and-recover evaluator — **the main build**
A script that takes the 343,865 well-located/well-dated events, synthetically coarsens them to
admin-1-or-country × year, runs a named allocation strategy, and scores the recovery against known
truth. Must emit: conservation check, earth-mover distance, mass-weighted hit rate at k, and slice
effective sample size. Must support stratification by event size and conflict intensity (the
declared confound in `02 §5`). Lives in `scripts/`, per the convention that `reports/investigation_*/`
holds prose and data but never `.py`.

### C2. Locked baselines
Three comparators computed once and frozen as a fixture: **O0 passthrough**, **uniform**, and
**oracle**. Without the uniform control, proportional weighting's extra assumption is unearned;
without oracle, we cannot tell near-ceiling from barely-started.

### C3. A parity-inertness test — **blocker**
A test asserting that `production_parity` output is byte-identical with every new strategy
registered but unselected. This is the test that makes "default-off" a fact rather than an intention,
and the repo's own `/falsify guard` discipline applies: break it and confirm it goes red.

### C4. A golden test for ADR-049's own acceptance criterion
ADR-049 specified that cell 148759 should drop from 273,076 to its proportional Tigray share. **No
test asserts this, which is why the divergence in `02 §3` stayed invisible for four months.** Write
the test. It should fail today — that is the point.

### C5. Conservation assertions at the new stage
Per ADR-040 Invariant 1 and ADR-049 §5, `Σ allocated == best` per event, with the rounding policy
declared. Note this is where `ceil_split`'s existing 0.91% inflation will surface as a red test; the
pre-registration must say whether that is in scope or deliberately excluded.

---

## D. Pre-flight checklist — must be green before the FIRST experiment

- [ ] **The two ADR-049 divergences resolved as governance** (`02 §3`) — **blocker**, and not an
      experiment. An accepted ADR must either be live or amended.
- [ ] `expert-method-review` run on `02_design`, specifically the coarsen-and-recover design and its
      declared proxy-population confound
- [ ] **C1** coarsen-and-recover evaluator implemented and unit-tested — **blocker**
- [ ] **C2** three locked baselines computed and frozen as a fixture
- [ ] **C3** parity-inertness test green, and **seen to fail** when deliberately broken — **blocker**
- [ ] **C4** ADR-049 golden test written (expected red until O1 lands)
- [ ] **C5** conservation assertions at the allocation stage; rounding policy declared
- [ ] any new strategy registered via `Registry`, not by editing the dispatcher
- [ ] full suite + `ruff` + `mypy --strict` green; contracts synced
- [ ] pre-analysis plan pre-registered via `/rnd-dossier preregister` (hypothesis + falsifiers +
      primary endpoint with a numeric threshold, against the locked baselines)
- [ ] `ceil_split` conservation violation and the ADR-049 divergences routed to `register-risk`

**`status` must refuse to call this program ready until the four blockers are green.**

---

## E. Rules of engagement

- **One variable at a time**, each behind its own profile key. Spatial and temporal allocation are
  two experiments, not one, however tempting the symmetry.
- **Pre-register, then run.** Falsifiers pre-committed; a fired falsifier kills the hypothesis and is
  not rescued ad hoc.
- **Cheap before expensive**: synthetic known-answer path → coarsen-and-recover on a stratified
  sample → the full 343,865-event run.
- **Behaviour-neutral by construction.** An improvement must come from better allocation, not from
  shrinking magnitudes. `Vesco2026` is the reason this matters: the large aggregates are the *most*
  accurately counted values we hold, so any remedy that quietly discounts them is masking, not
  fixing. The scale-invariant comparison (`02 §5`, metric 5) is the guard.
- **Never run concurrently with a production pipeline run** on the same host.
- ⭐ **A pre-registered number is evidence only if it is measured at the layer the consumer reads.**
  Added 2026-11-12 after the v1.18.0 release was verified against eight pre-registered numbers,
  passed all eight, and shipped a defect that made the allocation it was grading unobservable.
  All eight were computed by grouping on `priogrid_gid` — the field the event compiler ignores,
  because `_place_events` re-derives the cell from `latitude`/`longitude`. Every number was
  arithmetically correct about a quantity no consumer receives. `evaluate_temporal_allocation.py`,
  `investigate_summary_event_concentration.py`, ADR-049, ADR-053 and this dossier all measured
  there; `11_allocator_spec.md` and this file contained **zero** mentions of `priogrid_gid`,
  `latitude`, `longitude` or compilation, so the spec never said how a decision reaches the grid
  and the harness never named the delivered layer as the place to look.

  Two corollaries, both paid for:

  - **Name the layer in the row, not in the prose.** A falsifier row that says "cell 148759 holds
    N" must say *where it was read* — served store, compiled grid, or viewpoint parquet. The
    delivered-layer reader here is `scripts/measure_allocation_delivery.py`, which goes through
    `datafactory_query.load_dataset`, the same entry point a model's dataloader calls.
  - **Never pre-register a single slice the old defect concentrated in.** December 2021 was chosen
    as the test month because that is where the previous pipeline dumped everything. After temporal
    spreading December holds a small share, so the cell read 1,782 — a 64× improvement — while the
    worst cell-month across the whole span was 32,390, a 3.5× one. **The single-month check
    flattered the result by a factor of 18.** Pre-register the extremum over the whole span.

- ⭐ **Recompute every metric from its definition; never assert one from a reported number.** Added
  2026-11-05 after a threshold-decomposition conclusion was green, plausible, quotable and wrong —
  mean Brier at unequally spaced thresholds was compared as heights when `CRPS = ∫ BS(t) dt` makes
  the contribution `BS(t) × dt`. One step from the definition overturned it (59.3% of the integral is
  in the tail, not at the boundary). Conservation is already specified this way (`Σ allocated ==
  best`, recomputed); every metric in `02 §5` must be too. A guard that compares a reported number
  against a stored number cannot catch this class of error at all.
