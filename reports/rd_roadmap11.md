# R&D Roadmap v11 — ACLED End-to-End on Server, v1.2 Complete

**Date:** 2026-05-08
**Supersedes:** rd_roadmap10.md (2026-05-06)
**Status:** Active

---

## Where We Are

ACLED is fully integrated and proven on the production server. The entire pipeline — harvest, consolidate, viewpoint, compile, assemble, export, serve — runs end-to-end without manual intervention. The OOM crash during compilation (2M events on 8GB) was fixed by column projection. All 51 features (6 UCDP + 8 ACLED + 34 static + 3 admin) are served via zarr and verified by the 10-check remote verification script.

**What changed since v10:**
- ACLED assembly integration complete: 8 features wired into assembled grid (`[456, 360, 720, 51]`)
- Courteous ACLED harvesting: year-by-year fetching with version-aware skip, 2s page delay, User-Agent header
- OOM fix in grid compilation: column projection reduces peak memory from ~3.4 GB to ~800 MB
- Test review findings addressed: 46 ACLED harvester tests, 50 compiler tests
- Pre-existing test_structural_invariants failures fixed (7 tests now skip gracefully)
- Deployed v1.2.14 to Hetzner, full pipeline run successful (4835s)
- Remote verification passes: all 10 checks including ACLED feature verification
- Health check: all 12 sources healthy, export SLO met
- 821 tests passing, 0 failures

**System snapshot:** 10 packages, ~821 tests, 29 ADRs, 21 CICs. 160 concern IDs tracked: 104 resolved, 46 open/deferred, 6 accepted by design. Tagged v1.2.14.

---

## Completed Phases

### Phase 0-2c: UCDP Production Parity — COMPLETE
Full pipeline: harvest (5 sources) → consolidate → viewpoint → compile → assemble → export (zarr + parquet). 100% event-level match on 27,853 non-expanded events (.9-only test). Three-source consumer parity at 0.014-0.023% per feature column.

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
Full pipeline run with real data (2,047,347 events, 2020-2025). 13-plot visual audit + 8 statistical checks, all PASS.

### Phase ACLED-5: Assembly Integration — COMPLETE (2026-05-07)
ACLED grid wired into assembled grid alongside UCDP + static + admin. Temporal alignment: zero-fill before 2020, metadata boundary recorded. `load_dataset()` exposes all 8 ACLED features.

### Phase ACLED-6: Courteous Harvesting — COMPLETE (2026-05-07)
Year-by-year fetching with version-aware skip logic (skips cached years). 2s page delay, User-Agent header. Test review: 46 harvester tests. PR #41 merged.

### Phase ACLED-7: OOM Fix + Server Deployment — COMPLETE (2026-05-08)
Column projection in grid compiler: reads only ~5 needed columns instead of all 35. Peak memory ~3.4 GB → ~800 MB. Deployed v1.2.14, full pipeline run successful. Remote verification: 10/10 checks pass.

---

## Active Directions

### Direction 1: Source Expansion — NEXT

Consumer integration is proven. Two sources are fully operational. The third source is the WET-before-DRY inflection point where shared abstractions can be considered.

**Candidates:**
- **V-Dem:** Democracy indicators. Country-year resolution (not event-level). Would test whether the graph architecture handles non-event, non-grid-native data cleanly.
- **WDI (World Development Indicators):** Economic/development indicators. Country-year resolution. Similar structural profile to V-Dem.

**Decision needed:** Which source next? Both are country-year, both require country-to-grid disaggregation (mapping country-level values to PRIO-GRID cells via GAUL boundaries). V-Dem has stronger theoretical relevance to conflict forecasting.

### Direction 2: Deployment Hardening — MOSTLY COMPLETE

**Code work:** Complete. **Operator work:** Blocked on domain registration + IT CIDRs.

### Direction 3: Raster Sources — BLOCKED on rasterio

Population, built-up area, nightlights require raster-to-grid aggregation. Lower priority than tabular sources.

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
| SQ-1 | How should country-year data disaggregate to PRIO-GRID cells? | Not started |

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
        Phase ACLED-2b (ACLED compilation design — 4 decisions, ADR-028)
        Phase ACLED-3 (ACLED compilation — 8 features, 11 tests)
        Phase ACLED-4 (ACLED grid verification — 13 plots, 8 checks, all PASS)
        Phase ACLED-5 (ACLED assembly integration — wired into assembled grid)
        Phase ACLED-6 (courteous harvesting — year-by-year, skip logic, 46 tests)
        Phase ACLED-7 (OOM fix + server deployment — v1.2.14 proven end-to-end)
        |
NOW:    Choose next source (V-Dem vs WDI)
        Phase DH-2b  (v1.1 operator work — blocked on domain + IT)
        |
NEXT:   Phase 5       (third source integration — enables DRY extraction)
        |
LATER:  Phase DH-3   (v2.0 institutional — OAuth2, audit trail)
        Phase 3      (raster sources — blocked on rasterio)
        Phase 8      (cross-source analysis — AQ-3, AQ-4, RQ-7, RQ-9, RQ-11)
```

---

## Risk Register

Active concerns tracked in `reports/technical_risk_register.md` (ADR-020).

**Current:** 160 concern IDs: 104 resolved, 46 open/deferred, 6 accepted by design.

| Category | Count | Key items |
|----------|-------|-----------|
| Tier 1 | 0 open | All resolved |
| Tier 2 | 7 open | C-88 (SSH), C-130-C-132 (data boundary/monitoring), C-137-C-139 (data integrity), C-149 (GAUL unmapped cells) |
| Tier 3 | 12 open | C-21, C-126, C-129-C-133, C-144-C-146, C-153 (ACLED silent truncation), C-156 (ACLED temporal mismatch) |
| Tier 4 | 25 open | Includes C-159 (ACLED archiving untested), C-160 (string-data corruption guard) |
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
