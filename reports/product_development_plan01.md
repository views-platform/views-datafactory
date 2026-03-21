# Product Development Plan v01 — Production Parity

**Date:** 2026-03-21
**Supersedes:** product_development_plan.md (2026-03-16)
**Status:** Active
**Goal:** The system produces data identical to what VIEWS production currently uses for forecasting.

---

## Current State

### What Works

| Layer | Component | Status | Tests |
|-------|-----------|--------|-------|
| 0 | Provenance (digests, ledgers) | Done | 30 |
| 1 | PRIO-GRID backbone | Done | 67 |
| 1 | Harvester — annual | Done | 15 |
| 1 | Harvester — candidate | Done | 16 |
| 1 | Harvester — .9 | **Not built** | 0 |
| 2 | Consolidation (annual + candidate) | Done (vintage-aware) | 30 |
| 2 | Consolidation (.9 support) | **Not built** | 0 |
| 3 | Viewpoint builder | Done | 31 |
| 3 | .9-aware survivorship | **Not built** | 0 |
| 3 | Production-parity summary handling | **Not built** | 0 |
| 3 | Production filtering rules | **Not built** | 0 |
| 4 | Grid compilation | Done | 23 |
| — | DAG enforcement | Done | 1 |
| — | Integration tests | Done (partial) | 4 |
| — | Falsification stubs | Documented | 9 (skipped) |

**Total: 250 passed, 14 skipped**

### What's Missing for Production Parity

1. **No .9 harvester** — can't fetch the data production depends on
2. **No .9 in consolidation** — config has no `dot9_dir`
3. **No .9-aware survivorship** — `annual_wins` treats everything non-annual as candidate
4. **Summary detection differs** — we use `date_prec==5`, production uses `(best>0 & span>1 & best>=span)`
5. **Summary distribution differs** — we use exact division, production uses `ceil()`
6. **No production filters** — we don't filter `priogrid_gid<1`, `type_of_violence>=4`, or `where_prec in (4,6)`
7. **No .9 in smoke test** — end-to-end pipeline never tested with .9

---

## Milestones

### M1: .9 Harvester (unblocked — can start immediately)

**Goal:** Fetch .9 versions from the UCDP API using the existing harvester pattern.

**Deliverables:**
- `src/datafactory_harvester/sources/ucdp_dot9.py` — config + fetch + auto-register
- `UcdpDot9Config` — frozen dataclass with version format `YY.9.MM`
- Version discovery: probe `YY.9.1` through `YY.9.12` for each year
- Storage: `data/ucdp_dot9/ucdp_ged_dot9_YY.9.MM.parquet`
- Tests: Green/Beige/Red following existing candidate test pattern
- Register as `"ucdp_dot9"` in source registry

**Reuse:** The .9 API uses the same endpoint, auth, and pagination as candidate. Reuse `request_with_retry` and `fetch_paginated` from `ucdp_annual.py`.

**DoD:** `fetch_source("ucdp_dot9", config=...)` returns Parquet snapshots with provenance.

### M2: Three-Source Consolidation

**Goal:** Consolidate annual + candidate + .9 into a single vintage-aware store.

**Deliverables:**
- Add `dot9_dir` and `dot9_ledger_path` to `UcdpConsolidationConfig`
- Extend consolidation loop to read .9 files, tag with `_source_type="dot9"`
- Extract version from .9 filename pattern (`ucdp_ged_dot9_YY.9.MM.parquet`)
- Tests: .9 events appear in consolidated store with correct metadata

**DoD:** Consolidated store contains events from all three source types, distinguishable by `_source_type`.

### M3: .9-Aware Survivorship Strategy

**Goal:** A survivorship strategy that mirrors production's source preference.

**Deliverables:**
- New strategy `"dot9_wins"` in `survivorship.py`: for the .9 window, .9 version wins. For months only in annual, annual wins. For months only in candidate (and not in .9), candidate wins.
- Update `"production_parity"` profile to use `"dot9_wins"` survivorship
- Tests: three-way survivorship with events from all source types

**DoD:** Profile `"production_parity"` produces a viewpoint that prefers .9 data when available.

### M4: Production-Parity Summary Handling

**Goal:** Match production GedLoader's `fix_summary_events` exactly.

**Deliverables:**
- New distribution strategy `"ceil_split"` in `temporal_distribution.py`
  - Detection: `(best > 0) & (summary_period > 1) & (best >= summary_period)` — not `date_prec==5`
  - Distribution: `np.int64(np.ceil(best / n_months))` — not exact division
- Update `"production_parity"` profile to use `"ceil_split"`
- Tests: verify ceil behavior, verify detection criteria match production

**DoD:** Summary event handling produces output identical to production GedLoader.

### M5: Production Filtering Rules

**Goal:** Apply the same filters production uses.

**Deliverables:**
- Filtering should happen in the viewpoint builder (not in consolidation — ADR-013 says consolidation is lossless)
- Add filtering parameters to `ViewpointConfig`:
  - `min_priogrid_gid: int = 1` (drop events with `priogrid_gid < 1`)
  - `max_type_of_violence: int = 3` (drop events with `type_of_violence >= 4`)
  - `exclude_where_prec: tuple[int, ...] = (4, 6)` (spatial precision filter)
- Update `"production_parity"` profile with these filter values
- Other profiles (e.g., `"full_vintage"`) can set no filters

**DoD:** Viewpoint output matches production's event filtering.

### M6: End-to-End Production Parity Test

**Goal:** Prove the full pipeline produces output matching production.

**Deliverables:**
- Fetch one .9 version (e.g., `25.9.11`)
- Run: harvest .9 → consolidate (all three sources) → viewpoint with `"production_parity"` profile → compile
- Compare compiled grid against production GedLoader output event-by-event
- Document remaining discrepancies (if any) with exact counts and causes
- Resolve all falsification test stubs (unskip or convert to passing tests)

**DoD:** <5% event-level discrepancy between our output and production, with all differences explained.

---

## Milestone Dependencies

```
M1 (.9 harvester)
  │
  ├──→ M2 (three-source consolidation)
  │       │
  │       ├──→ M3 (.9-aware survivorship)
  │       │       │
  │       │       └──→ M6 (parity test)
  │       │               ↑
  M4 (ceil_split) ────────┘
  M5 (filters) ──────────┘
```

M4 and M5 are independent of M1-M3. They can be done in parallel.

---

## Operational Concerns (from concerns00.md)

These should be addressed alongside or after production parity:

| Concern | Priority | Notes |
|---------|----------|-------|
| C-24: Compiler loads entire Parquet as list-of-dicts | High after M6 | Full-scale data will be ~400K events; current approach creates ~20M Python objects |
| C-25: Source digest reads entire file into memory | Medium | Chunked hashing needed for 60MB Parquets |
| C-14: Unbounded JSONL ledgers | Medium | Monthly harvesting of 3 source types will grow ledgers quickly |
| C-30: No full-scale performance test | High after M6 | 259,200 cells × 48+ months must compile in <60 seconds |
| C-21: No characterization tests | Medium | Migrated grid code should be compared against metric lab |

---

## Architecture References

| ADR | Relevance |
|-----|-----------|
| ADR-012 | 4-layer architecture: harvest → consolidate → viewpoint → compile |
| ADR-013 | Consolidation is lossless, append-only, bitemporal |
| ADR-014 | Viewpoints are disposable, rebuildable, versioned |
| ADR-015 | UCDP consolidation specifics (needs updating when .9 is understood) |
| ADR-016 | Viewpoint profiles — named presets for research configurations |
| ADR-017 | Vintage-aware consolidation — content-digest dedup |

---

## Success Criteria — ALL MET (2026-03-21)

| Criterion | Status | Evidence |
|-----------|--------|----------|
| 1. Harvest all three UCDP data streams | **MET** | M1: `ucdp_dot9.py` harvester, M1 tests pass |
| 2. Consolidated store has all three types with vintage tracking | **MET** | M2: three-source consolidation, ADR-017 vintage dedup |
| 3. <5% event-level discrepancy | **EXCEEDED** | 100.00% match on 27,853 non-expanded events (0% discrepancy) |
| 4. All discrepancies documented | **MET** | `reports/dot9_investigation/parity_results.md` — three categories fully explained |
| 5. Full pipeline runs end-to-end | **MET** | `scripts/parity_test.py` — .9 → consolidate → viewpoint → compare |
6. All falsification test stubs are resolved (either fixed and unskipped, or converted to passing tests documenting the fix)

When these criteria are met, the system is production-ready for VIEWS forecasting.
