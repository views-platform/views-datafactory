# R&D Roadmap v06 — Consumer Parity Achieved

**Date:** 2026-04-08
**Supersedes:** rd_roadmap05.md (2026-04-07)
**Status:** Active

---

## Where We Are

The data factory produces UCDP conflict data at verified consumer parity, serves it from Hetzner, and has a working consumer API. A forensic parity investigation (April 2026) identified and resolved the root cause of the remaining discrepancy between our output and VIEWSER's gold set: VIEWSER applies summary event distribution selectively by source type. This finding was codified as a configurable `source_distribution_map` on ViewpointConfig.

The consumer API (`datafactory_query`) is feature-complete for local access: `load_dataset()` handles regions, temporal subsetting, feature selection, and multiple output formats. Consumer parity tests against the VIEWSER gold set pass. The focus shifts to **first real consumer integration** and **remote access validation**.

**System snapshot:** 10 packages, 511 tests, 25 ADRs, 15 CICs. 115 concern IDs tracked: 80 resolved, 27 open/deferred, 6 accepted by design.

---

## Completed Phases

### Phase 0-2c: UCDP Production Parity — COMPLETE
Full pipeline: harvest (5 sources) → consolidate → viewpoint → compile → assemble → export (zarr + parquet). 100% event-level match on 27,853 non-expanded events (.9-only test). Three-source consumer parity at 0.014-0.023% per feature column — residual is annual version difference, not a code defect. See `reports/consumer_parity_investigation.md` and `reports/dot9_investigation/parity_results.md`.

Key finding: VIEWSER applies `fix_summary_events=False` for annual data and `fix_summary_events=True` (ceil rounding) for .9 data. This mixed behavior is now configurable via `source_distribution_map` on ViewpointConfig. Non-configurable invariants documented in ADR-023.

### Phase 2d: Data Serving Infrastructure — COMPLETE
Caddy on Hetzner, basic auth, cron, 10-check verification, consumer guides. See `docs/guides/hetzner_deployment_guide.md`.

### Phase DH-1: v1.0 Deployment Hardening — COMPLETE (2026-04-02)
Export timestamp, main branch current, v1.0.0 tagged, logrotate, e2e integration test.

### Phase DH-2a: v1.1 Code Work — COMPLETE (2026-04-07)
Tag-based deployment gate (ADR-022), freshness SLO (168h, ADR-018), health check tests, atomic assembly writes, version parsing hardening, date format validation, shared adapter validation, timeout policy documented.

### Phase CA-1: Consumer API MVP — COMPLETE (2026-04-08)
`datafactory_query` package with:
- `load_dataset()`: unified entry point for all consumer access
- 8 predefined regions (Africa, Middle East, Americas, Europe, Asia-Oceania, Africa+ME, global, land) + country-level lookup via GAUL
- Temporal parsing: ISO strings, VIEWS month_ids, year-only, None defaults
- Output formats: FeatureFrame, DataFrame
- Zarr support: local and remote paths via xarray + fsspec
- Consumer parity: 3 tests (DataFrame, FeatureFrame, zarr) pass against VIEWSER gold set
- 37 query/parity tests, import enforcement updated

Config promotion (same phase):
- ViewpointConfig: `filter_stale_versions`, `source_distribution_map` — all viewpoint research choices now configurable
- CompilationConfig: `output_dtype`, `fill_value`, `FeatureSpec.value_field` — grid output parameters configurable
- Aggregation strategies renamed: `sum_field`/`max_field` (old `sum_best`/`max_best` kept as aliases)

---

## Active Directions

### Direction 1: Consumer Integration — CURRENT FOCUS

**Problem solved:** The consumer API exists and is verified against the gold set. What remains is proving it works with real training scripts and over the network.

**Open questions:**

| ID | Question | Status |
|----|----------|--------|
| CQ-1 | Does `load_dataset()` perform acceptably on the full 19 GB grid? | **Answered** — consumer parity tests run in ~30s on full assembled grid |
| CQ-2 | Is the region definition complete and correct? | **Answered** — consumer parity tests validate against 13,110 VIEWSER pgids (Africa+ME+South Asia) |
| CQ-3 | Should the remote path use the same interface? | **Answered** — yes, `load_dataset(data_dir="http://...")` uses zarr path transparently |
| CQ-4 | What does the training script actually need? | Pending first integration |
| CQ-5 | Should xarray Dataset be a supported output format? | Deferred |
| CQ-6 | Where should transformations live? | Deferred |

**Next steps:**
1. Integrate with first training script (purple_alien) — let friction surface
2. Smoke test remote zarr path against live server
3. Merge development → main, tag v1.2
4. Write ADR-025 (query layer architecture) once interface is proven with real consumers

### Direction 2: New Data Sources — PAUSED

Unchanged from v05. Integration deferred until the consumer path is proven with real training scripts.

| Source | Type | Resolution | Status | Dependency |
|--------|------|-----------|--------|------------|
| V-Dem | Democracy indicators | Country-year | Investigation | Consumer integration proven |
| ACLED | Conflict + protests | Point events | Blocked (access) | Consumer integration proven |
| WID | Inequality | Country-year | Investigation | Consumer integration proven |

### Direction 3: Raster Sources — BLOCKED on rasterio

Unchanged. Population, built-up area, nightlights require raster-to-grid aggregation. Blocked on rasterio/GDAL dependency.

### Direction 4: Deployment Hardening — MOSTLY COMPLETE

**Code work:** Complete. All v1.1 code criteria met.

**Operator work:** Blocked on external parties.

| Task | Blocker | Status |
|------|---------|--------|
| Domain registration + HTTPS | Domain not registered | Blocked |
| SSH IP restriction | IT hasn't provided CIDRs | Blocked |
| Service account + deploy key | Requires SSH to server | Procedure documented |
| Named user accounts | Requires SSH to server | Procedure documented |

---

## Research Questions

### Existing (from v04)

| RQ | Topic | Status |
|----|-------|--------|
| RQ-1 | What is the .9 data stream? | Awaiting UCDP response |
| RQ-2 | Candidate mutability | Partially answered |
| RQ-3 | Can .9 be reconstructed? | Answered: NO |
| RQ-4 | What is production parity? | **Answered** — see `consumer_parity_investigation.md` |
| RQ-5 | Statistical profile of data | Ready to start |
| RQ-6 | Revision history analysis | Needs full harvest |

### Consumer API

| RQ | Topic | Status |
|----|-------|--------|
| CQ-1 | Performance on full grid | **Answered** (~30s) |
| CQ-2 | Region definition completeness | **Answered** (validated via parity tests) |
| CQ-3 | Unified vs split local/remote interface | **Answered** (unified) |
| CQ-4 | What does the training script actually need? | Pending first integration |
| CQ-5 | xarray as output format | Deferred |
| CQ-6 | Transformation boundary (server vs client) | Deferred |

### Source expansion (unchanged)

| RQ | Topic | Status |
|----|-------|--------|
| RQ-7 | Do democracy indicators predict conflict? | Not started |
| RQ-8 | Does ACLED coverage predict UCDP violence? | Not started |
| RQ-9 | Does inequality predict subnational conflict? | Not started |
| RQ-10 | How do UCDP and ACLED compare? | Not started |
| RQ-11 | Can inequality trends serve as risk indicators? | Not started |

---

## Phase Roadmap

```
DONE:   Phase 0-2c   (UCDP production parity)
        Phase 2d     (data serving infrastructure)
        Phase DH-1   (v1.0 deployment hardening, tagged v1.0.0)
        Phase DH-2a  (v1.1 code work, tagged v1.1.0)
        Phase CA-1   (consumer API MVP + parity investigation)
        |
NOW:    Phase CA-2   (first training script integration)
        Phase DH-2b  (v1.1 operator work — blocked on domain + IT)
        |
NEXT:   Phase CA-3   (remote zarr smoke test)
        Merge to main + tag v1.2
        |
THEN:   Phase 5      (V-Dem integration — country-level broadcast)
        Phase 6      (ACLED integration — second conflict source)
        |
LATER:  Phase DH-3   (v2.0 institutional — OAuth2, audit trail)
        Phase 7      (WID integration — inequality indicators)
        Phase 3      (raster sources — blocked on rasterio)
        Phase 8      (cross-source analysis — RQ-7 through RQ-11)
```

---

## Risk Register

Active concerns tracked in `reports/technical_risk_register.md` (ADR-020).

**Current:** 115 concern IDs: 80 resolved, 27 open/deferred, 6 accepted by design.

| Category | Count | Key items |
|----------|-------|-----------|
| Tier 1 | 0 open | All resolved |
| Tier 2 | 5 open | C-84-C-88 (server hardening, blocked on external) |
| Tier 3 | 1 open | C-21 (characterization tests) |
| Tier 4 | 15 open | Most untriggered; 2 accepted at v1.0; C-115 new (summary detection threshold) |
| Accepted | 6 | C-06, C-07, C-10, C-32, C-38, C-41 |
