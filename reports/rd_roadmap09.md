# R&D Roadmap v09 — ACLED Phase 2 Complete, Compilation Decisions Resolved

**Date:** 2026-05-05
**Supersedes:** rd_roadmap08.md (2026-05-03)
**Status:** Active

---

## Where We Are

ACLED Phase 2 (proof-of-access) is complete: the harvester has been validated against the real ACLED API, fixed to match the actual OAuth2 + pagination model, and all tests pass (70 ACLED-related tests). The four compilation design decisions (spatial, temporal, features, granularity) have been resolved from first principles in a clean-room process and documented in ADR-028.

**What changed since v08:**
- Harvester validated against real ACLED API — OAuth2 password grant, page-based pagination, response envelope with `count: null, total_count: null`
- Fixed event_types config to wire through to API query filter (was validated in config but never sent)
- C-153 registered: ACLED API silent truncation risk (Tier 3)
- C-72 updated: 429/rate-limiting concern now includes ACLED
- ADR-028 written: ACLED consolidation and viewpoint specifics (clean-room design rationale)
- ADR-015 updated: UCDP viewpoint v1 rationale made explicit (parity target, not design ideal)
- All four ACLED compilation decisions resolved (ADR-028):
  1. Spatial: lat/lon → cell, all geo_precision values, same as UCDP
  2. Temporal: 1:1, one event = one date = one month (ACLED events are atomic daily records)
  3. Features: 8 columns per cell-month (total count, 6 per-type counts, fatalities sum)
  4. Granularity: per event_type (6 types), not sub_event_type (~25)

**WET-before-DRY awareness:** Unchanged. Two sources, no shared abstractions until V-Dem. The ACLED compilation will follow the same `FeatureSpec` pattern as UCDP (ADR-024) but remain an independent implementation.

**System snapshot:** 10 packages, ~740 tests, 29 ADRs, 21 CICs. 153 concern IDs tracked: 99 resolved, 46 open/deferred, 6 accepted by design.

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

### Phase ACLED-0: ACLED Infrastructure — COMPLETE (2026-05-03)
Harvester, consolidator, viewpoint builder built from UCDP patterns and ACLED API documentation. 62 tests, 4 CICs.

### Phase ACLED-2: ACLED Proof-of-Access — COMPLETE (2026-05-05)
Validated harvester against real ACLED API. Fixed OAuth2 flow, pagination model, and event_types filter. Falsification audit passed. 70 tests (including 2 new falsification tests for event_type filter). PR #35 merged.

Key findings:
- OAuth2: POST to `https://acleddata.com/oauth/token` with `client_id=acled`, form-encoded
- API: `https://acleddata.com/api/acled/read`, page-based pagination, `_format=json`
- Response envelope: `{"status": 200, "success": true, "count": null, "total_count": null, "data": [...]}`
- No TotalCount verification possible (ADR-027, C-153)
- ACLED events are atomic single-day records — multi-day conflicts are separate daily events

### Phase ACLED-2b: Compilation Design — COMPLETE (2026-05-05)
Clean-room design discussion resolving all four compilation decisions. Documented in ADR-028. No reference to legacy ingestor — decisions made from first principles.

---

## Active Directions

### Direction 1: Consumer Integration — CURRENT FOCUS

**Problem solved:** The consumer API exists and is verified. What remains is proving it works with real training scripts.

**Next steps:**
1. Integrate with first training script (bright_starship)
2. Merge development → main, tag v1.2

### Direction 2: ACLED Phase 3 — Compilation — READY TO BUILD

**Problem:** The design is resolved (ADR-028). The compilation step that transforms ACLED events into `(cells, time, features)` grid npy arrays does not exist yet.

**What needs building:**
1. ACLED compiler following the `FeatureSpec` pattern (ADR-024)
2. 8 features: `acled_count`, `acled_battles`, `acled_explosions`, `acled_vac`, `acled_protests`, `acled_riots`, `acled_strategic`, `acled_fatalities`
3. Spatial: lat/lon → PRIO-GRID cell (same as UCDP)
4. Temporal: event_date month → time index
5. Tests: compilation output correctness, feature counts match expectations
6. Assembly: integrate ACLED features into the assembled grid alongside UCDP

**What does NOT need building:**
- No survivorship logic (single source)
- No temporal distribution (atomic daily events)
- No geo_precision handling (assign all, noise accepted)
- No sub-event-type features (deferred)
- No actor features (deferred, cross-source design effort)

### Direction 3: V-Dem — INVESTIGATION

V-Dem would be the **third data source** — the point at which WET-before-DRY allows extracting shared patterns (if any exist). Country-year resolution (not event-level).

### Direction 4: Raster Sources — BLOCKED on rasterio

Unchanged. Population, built-up area, nightlights require raster-to-grid aggregation.

### Direction 5: Deployment Hardening — MOSTLY COMPLETE

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
| CQ-4 | What does the training script actually need? | Pending first integration |
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
        Phase ACLED-0 (ACLED infrastructure — harvester, consolidator, viewpoint, tests, CICs)
        Phase ACLED-2 (ACLED proof-of-access — real API validated, harvester fixed)
        Phase ACLED-2b (ACLED compilation design — 4 decisions resolved, ADR-028)
        |
NOW:    Phase CA-2b  (first training script integration — M11)
        Phase DH-2b  (v1.1 operator work — blocked on domain + IT)
        |
NEXT:   Phase ACLED-3 (ACLED compilation — build the compiler, 8 features)
        Merge to main + tag v1.2
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

**Current:** 153 concern IDs: 99 resolved, 46 open/deferred, 6 accepted by design.

| Category | Count | Key items |
|----------|-------|-----------|
| Tier 1 | 0 open | All resolved |
| Tier 2 | 7 open | C-88 (SSH), C-130–C-132 (data boundary/monitoring), C-137–C-139 (data integrity), C-149 (GAUL unmapped cells) |
| Tier 3 | 11 open | C-21, C-126, C-129–C-133, C-144–C-146, C-153 (ACLED silent truncation) |
| Tier 4 | 22 open | Most untriggered; 2 accepted at v1.0 |
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
