# R&D Roadmap v05 — Consumer Readiness

**Date:** 2026-04-07
**Supersedes:** rd_roadmap04.md (2026-04-02)
**Status:** Active

---

## Where We Are

The data factory produces UCDP conflict data at production parity, serves it from Hetzner, and has passed two rounds of deployment hardening. The system is operationally stable: v1.0 tagged, v1.1 in progress (blocked on external dependencies).

The focus has shifted from **"does it work?"** to **"can others use it?"** The first real consumer — an automated training script — is imminent. A new `datafactory_query` package provides temporal + geographic subsetting, but the interface is untested with real consumers and the remote access path is not implemented.

**System snapshot:** 10 packages, 470 tests, 23 ADRs, 16 CICs. 113 concern IDs tracked: 79 resolved, 26 open/deferred, 6 accepted by design.

---

## Completed Phases

### Phase 0-2c: UCDP Production Parity — COMPLETE
Full pipeline: harvest (5 sources) → consolidate → viewpoint → compile → assemble → export (zarr + parquet). 100% event-level match on 27,853 non-expanded events. See `rd_roadmap02.md`.

### Phase 2d: Data Serving Infrastructure — COMPLETE
Caddy on Hetzner, basic auth, cron, 10-check verification, consumer guides. See `docs/guides/hetzner_deployment_guide.md`.

### Phase DH-1: v1.0 Deployment Hardening — COMPLETE (2026-04-02)
Export timestamp, main branch current, v1.0.0 tagged, logrotate, e2e integration test.

### Phase DH-2a: v1.1 Code Work — COMPLETE (2026-04-07)
Tag-based deployment gate (ADR-022), freshness SLO (168h, ADR-018), health check tests, atomic assembly writes, version parsing hardening, date format validation, shared adapter validation, timeout policy documented. Server hardening procedures documented but blocked on external actions (domain, IT CIDRs).

---

## Active Directions

### Direction 1: Consumer API — NEW (current focus)

**Problem:** Training scripts need to pull subsets of the assembled grid by region and time range, in formats suitable for model training (FeatureFrame, DataFrame). Currently, consumers must load the full grid, manually build pgid masks, slice, and convert. This is fragile and creates friction.

**What exists:** `datafactory_query` package (MVP) with:
- Region definitions: 8 predefined regions + country-level lookup via GAUL
- Temporal parsing: ISO strings, VIEWS month_ids, year-only, None defaults
- Unified `load_dataset()`: region + time + features + format → FeatureFrame or DataFrame
- 23 tests, import enforcement updated

**Open questions:**

| ID | Question | Status |
|----|----------|--------|
| CQ-1 | Does `load_dataset()` perform acceptably on the full 19 GB grid? | Untested with real data |
| CQ-2 | Is the region definition complete and correct? (203 GAUL countries → 6 macro-regions) | Needs validation |
| CQ-3 | Should the remote path (zarr over HTTP) use the same `load_dataset()` interface or a separate function? | Design decision pending |
| CQ-4 | What does the training script actually need? (confirmed by first consumer integration) | Pending |
| CQ-5 | Should xarray Dataset be a supported output format alongside FeatureFrame and DataFrame? | Deferred |
| CQ-6 | Where should transformations live — server-side, client-side, or shared? | Deferred |

**Next steps:**
1. Smoke test with real assembled grid on Hetzner
2. Integrate with first training script — let friction surface
3. Add remote/zarr path once local path is proven
4. Write ADR-023 once interface stabilizes

### Direction 2: New Data Sources — PAUSED

Three sources investigated. Integration deferred until the consumer API is proven with UCDP-only models. The system supports UCDP-only training workflows today.

| Source | Type | Resolution | Status | Dependency |
|--------|------|-----------|--------|------------|
| V-Dem | Democracy indicators | Country-year | Investigation | Consumer API stable |
| ACLED | Conflict + protests | Point events | Blocked (access) | Consumer API stable |
| WID | Inequality | Country-year | Investigation | Consumer API stable |

**Rationale for pause:** Adding sources before the consumer interface is proven would multiply the testing surface without a clear consumer. Better to validate the full path (harvest → serve → consume) with UCDP first, then extend.

### Direction 3: Raster Sources — BLOCKED on rasterio

Unchanged. Population, built-up area, nightlights require raster-to-grid aggregation. Blocked on rasterio/GDAL dependency.

### Direction 4: Deployment Hardening — MOSTLY COMPLETE

**Code work:** Complete. All v1.1 code criteria met (deployment gate, freshness SLO, production hardening).

**Operator work:** Blocked on external parties.

| Task | Blocker | Status |
|------|---------|--------|
| Domain registration + HTTPS | Domain not registered | Blocked |
| SSH IP restriction | IT hasn't provided CIDRs | Blocked |
| Service account + deploy key | Requires SSH to server | Procedure documented |
| Named user accounts | Requires SSH to server | Procedure documented |

**v2.0 (institutional):** Not started. Requires OAuth2, per-user audit trail. ~3-4 weeks when prioritized.

---

## Research Questions

### Existing (from v04)

| RQ | Topic | Status |
|----|-------|--------|
| RQ-1 | What is the .9 data stream? | Awaiting UCDP response |
| RQ-2 | Candidate mutability | Partially answered |
| RQ-3 | Can .9 be reconstructed? | Answered: NO |
| RQ-4 | What is production parity? | Answered |
| RQ-5 | Statistical profile of data | Ready to start |
| RQ-6 | Revision history analysis | Needs full harvest |

### Consumer API (new)

| RQ | Topic | Status |
|----|-------|--------|
| CQ-1 | Performance on full grid | Untested |
| CQ-2 | Region definition completeness | Needs validation |
| CQ-3 | Unified vs split local/remote interface | Design pending |
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
        Phase DH-2a  (v1.1 code work complete)
        |
NOW:    Phase CA-1   (consumer API MVP — datafactory_query on branch)
        Phase DH-2b  (v1.1 operator work — blocked on domain + IT)
        |
NEXT:   Phase CA-2   (first training script integration + smoke test)
        Phase CA-3   (remote/zarr path in load_dataset)
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

**Current:** 113 concern IDs: 79 resolved, 26 open/deferred, 6 accepted by design.

| Category | Count | Key items |
|----------|-------|-----------|
| Tier 1 | 0 open | All resolved |
| Tier 2 | 5 open | C-84–C-88 (server hardening, blocked on external) |
| Tier 3 | 1 open | C-21 (characterization tests) |
| Tier 4 | 14 open | Most untriggered; 2 accepted at v1.0 |
| Accepted | 6 | C-06, C-07, C-10, C-32, C-38, C-41 |
