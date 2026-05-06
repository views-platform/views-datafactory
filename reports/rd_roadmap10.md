# R&D Roadmap v10 — ACLED Compilation + Grid Verification Complete

**Date:** 2026-05-06
**Supersedes:** rd_roadmap09.md (2026-05-05)
**Status:** Active

---

## Where We Are

ACLED Phase 3 (compilation) and Phase 4 (grid verification) are complete. The full ACLED pipeline has been run end-to-end with real data: 2,047,347 events harvested, consolidated, viewpointed, and compiled to a `[72, 360, 720, 8]` grid. 13-plot visual verification + 8 statistical checks all pass. Training scripts (bright_starship, heavy_freighter, heavy_strider, light_strider) are integrated with the consumer API.

**What changed since v09:**
- ACLED compilation built and tested (ADR-028): `scripts/compile_acled.py`, 11 tests
- Full ACLED pipeline run end-to-end: harvest → consolidate → viewpoint → compile
- Grid verification script (`scripts/verify_acled_grid.py`): 13 plots, 8 checks, all PASS
- Pipeline orchestrator (`scripts/run_acled_pipeline.py`)
- C-154 registered: ACLED_FEATURES config duplication (Tier 4)
- C-155 registered: no shared visual audit framework (Tier 4)
- C-156 registered: ACLED temporal range mismatch — zero-fill before 2020 (Tier 3)
- Training script integration (M11) confirmed complete

**WET-before-DRY awareness:** Unchanged. Two sources, no shared abstractions until V-Dem. ACLED compilation follows the same `FeatureSpec` pattern as UCDP (ADR-024) but is an independent implementation. Visual audit scripts are similarly per-source (C-155).

**System snapshot:** 10 packages, ~778 tests, 29 ADRs, 21 CICs. 156 concern IDs tracked: 104 resolved, 44 open/deferred, 6 accepted by design.

---

## Completed Phases

### Phase 0-2c: UCDP Production Parity — COMPLETE
Full pipeline: harvest (5 sources) → consolidate → viewpoint → compile → assemble → export (zarr + parquet). 100% event-level match on 27,853 non-expanded events (.9-only test). Three-source consumer parity at 0.014-0.023% per feature column. See `reports/consumer_parity_investigation.md`.

### Phase 2d: Data Serving Infrastructure — COMPLETE
Caddy on Hetzner, basic auth, cron, 10-check verification, consumer guides.

### Phase DH-1: v1.0 Deployment Hardening — COMPLETE (2026-04-02)
Export timestamp, main branch current, v1.0.0 tagged, logrotate, e2e integration test.

### Phase DH-2a: v1.1 Code Work — COMPLETE (2026-04-07)
Tag-based deployment gate (ADR-022), freshness SLO (168h, ADR-018), health check tests, atomic assembly writes.

### Phase CA-1: Consumer API MVP — COMPLETE (2026-04-08)
`datafactory_query` with `load_dataset()`, regions, temporal parsing, FeatureFrame/DataFrame output, zarr support.

### Phase CA-2a: Verification Examples Suite — COMPLETE (2026-04-21)
15 standalone verification scripts, all passing. Remote zarr smoke test passes.

### Phase CA-2b: Training Script Integration — COMPLETE (2026-05-06)
Consumer API integrated with bright_starship, heavy_freighter, heavy_strider, light_strider. M11 complete.

### Phase ACLED-0: ACLED Infrastructure — COMPLETE (2026-05-03)
Harvester, consolidator, viewpoint builder built from UCDP patterns and ACLED API documentation. 62 tests, 4 CICs.

### Phase ACLED-2: ACLED Proof-of-Access — COMPLETE (2026-05-05)
Validated harvester against real ACLED API. Fixed OAuth2 flow, pagination model, and event_types filter. 70 tests.

### Phase ACLED-2b: Compilation Design — COMPLETE (2026-05-05)
Clean-room design discussion resolving all four compilation decisions. Documented in ADR-028.

### Phase ACLED-3: Compilation — COMPLETE (2026-05-06)
ACLED compiler built: `scripts/compile_acled.py` with 8 `FeatureSpec` columns (ADR-028). 11 compilation tests. Grid output: `[72, 360, 720, 8]` float32.

### Phase ACLED-4: Grid Verification — COMPLETE (2026-05-06)
Full pipeline run with real data (2,047,347 events, 2020–2025). 13-plot visual audit + 8 statistical checks, all PASS. Verified: correct geographic placement, plausible type distribution, structural invariant holds everywhere, annual counts 269k–411k, Gini=0.954, all spot-check cities have nonzero events with correct dominant types.

---

## Active Directions

### Direction 1: ACLED Assembly Integration — CURRENT FOCUS

**Problem:** ACLED is compiled but not yet wired into the assembled grid. `load_dataset()` cannot serve ACLED features. Training scripts cannot fetch ACLED data.

**What needs building:**
1. Update `scripts/assemble_grid.py` to load ACLED compiled grid and concatenate 8 features
2. Handle temporal alignment: UCDP 1989–present, ACLED 2020–present → zero-fill ACLED before 2020 (C-156)
3. Update zarr export to include ACLED features
4. Verify `load_dataset()` exposes ACLED features correctly

**Design decision (accepted):** Zero-fill ACLED channels before 2020. Temporal alignment deferred to later iteration (C-156).

### Direction 2: V-Dem — INVESTIGATION

V-Dem would be the **third data source** — the point at which WET-before-DRY allows extracting shared patterns (if any exist). Country-year resolution (not event-level).

### Direction 3: Raster Sources — BLOCKED on rasterio

Unchanged. Population, built-up area, nightlights require raster-to-grid aggregation.

### Direction 4: Deployment Hardening — MOSTLY COMPLETE

**Code work:** Complete. **Operator work:** Blocked on domain registration + IT CIDRs.

---

## Research Questions

### Existing (from v04)

| RQ | Topic | Status |
|----|-------|--------|
| RQ-1 | What is the .9 data stream? | Awaiting UCDP response |
| RQ-2 | Candidate mutability | Partially answered |
| RQ-3 | Can .9 be reconstructed? | Answered: NO |
| RQ-4 | What is production parity? | **Answered** |
| RQ-5 | Statistical profile of data | Ready to start |
| RQ-6 | Revision history analysis | Needs full harvest |

### Consumer API

| RQ | Topic | Status |
|----|-------|--------|
| CQ-1 | Performance on full grid | **Answered** (~30s) |
| CQ-2 | Region definition completeness | **Answered** |
| CQ-3 | Unified vs split local/remote interface | **Answered** (unified) |
| CQ-4 | What does the training script actually need? | **Answered** (integrated with 4 scripts) |
| CQ-5 | xarray as output format | Deferred |
| CQ-6 | Transformation boundary (server vs client) | Deferred |

### ACLED

| RQ | Topic | Status |
|----|-------|--------|
| AQ-1 | Does the real ACLED API match our assumed pagination model? | **Answered** — page-based, confirmed 2026-05-05 |
| AQ-2 | Does the ACLED event schema match our REQUIRED_FIELDS? | **Answered** — schema validated against real API response |
| AQ-3 | Does ACLED coverage predict UCDP violence? | Not started |
| AQ-4 | How do UCDP and ACLED event counts compare? | Not started |

### Source expansion

| RQ | Topic | Status |
|----|-------|--------|
| RQ-7 | Do democracy indicators predict conflict? | Not started |
| RQ-9 | Does inequality predict subnational conflict? | Not started |
| RQ-11 | Can inequality trends serve as risk indicators? | Not started |

---

## Phase Roadmap

```
DONE:   Phase 0-2c   (UCDP production parity)
        Phase 2d     (data serving infrastructure)
        Phase DH-1   (v1.0 deployment hardening, tagged v1.0.0)
        Phase DH-2a  (v1.1 code work, tagged v1.1.0)
        Phase CA-1   (consumer API MVP + parity investigation)
        Phase CA-2a  (verification examples suite)
        Phase CA-2b  (training script integration — M11)
        Phase ACLED-0 (ACLED infrastructure — harvester, consolidator, viewpoint, tests, CICs)
        Phase ACLED-2 (ACLED proof-of-access — real API validated, harvester fixed)
        Phase ACLED-2b (ACLED compilation design — 4 decisions resolved, ADR-028)
        Phase ACLED-3 (ACLED compilation — 8 features, 11 tests)
        Phase ACLED-4 (ACLED grid verification — 13 plots, 8 checks, all PASS)
        |
NOW:    Phase ACLED-5 (ACLED assembly integration — wire into assembled grid)
        Phase DH-2b  (v1.1 operator work — blocked on domain + IT)
        |
NEXT:   Merge to main + tag v1.2.11
        Deploy to Hetzner
        |
THEN:   Phase 5       (V-Dem integration — third source, enables DRY extraction)
        |
LATER:  Phase DH-3   (v2.0 institutional — OAuth2, audit trail)
        Phase 7      (WID integration — inequality indicators)
        Phase 3      (raster sources — blocked on rasterio)
        Phase 8      (cross-source analysis — AQ-3, AQ-4, RQ-7, RQ-9, RQ-11)
```

---

## Risk Register

Active concerns tracked in `reports/technical_risk_register.md` (ADR-020).

**Current:** 156 concern IDs: 104 resolved, 44 open/deferred, 6 accepted by design.

| Category | Count | Key items |
|----------|-------|-----------|
| Tier 1 | 0 open | All resolved |
| Tier 2 | 7 open | C-88 (SSH), C-130–C-132 (data boundary/monitoring), C-137–C-139 (data integrity), C-149 (GAUL unmapped cells) |
| Tier 3 | 12 open | C-21, C-126, C-129–C-133, C-144–C-146, C-153 (ACLED silent truncation), C-156 (ACLED temporal mismatch) |
| Tier 4 | 23 open | Most untriggered; 2 accepted at v1.0 |
| Accepted | 6 | C-06, C-07, C-10, C-32, C-38, C-41 |

---

## Architecture References

| ADR | Relevance |
|-----|-----------|
| ADR-012 | 4-layer graph architecture |
| ADR-013 | Consolidation: lossless, append-only, bitemporal |
| ADR-014 | Viewpoints: disposable, rebuildable, versioned |
| ADR-015 | UCDP consolidation + viewpoint specifics (parity rationale) |
| ADR-016 | Viewpoint profiles — constitutional, applies to all sources |
| ADR-017 | Vintage-aware consolidation (content-digest dedup) |
| ADR-018 | Operational resilience + timeout policy + freshness SLO |
| ADR-020 | Technical risk register |
| ADR-021 | Zarr export format |
| ADR-022 | Tag-based deployment gate |
| ADR-023 | Viewpoint builder invariants |
| ADR-024 | Compilation grid invariants |
| ADR-026 | Credential management — UCDP token + ACLED OAuth2 |
| ADR-027 | Harvest count verification — ACLED has no TotalCount |
| ADR-028 | ACLED consolidation + viewpoint specifics (clean-room design rationale) |
