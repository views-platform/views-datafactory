# R&D Roadmap v08 — ACLED Phase 0 Complete

**Date:** 2026-05-03
**Supersedes:** rd_roadmap07.md (2026-04-21)
**Status:** Active

---

## Where We Are

ACLED Phase 0 (infrastructure) is complete: harvester, consolidator, viewpoint builder, 62 tests (including 13 Red team), 4 CICs, credential setup guide, and full documentation alignment. C-150/C-151/C-152 (test coverage gaps from integration test review) are resolved.

**However, Phase 0 was built from UCDP patterns and ACLED API documentation — not from real API interaction.** The harvester, consolidator, and viewpoint builder mirror UCDP's architecture. If the real ACLED API differs substantially (different pagination model, different response envelope, nested data, different event schema), the harvester will need significant rework. The consolidator and viewpoint builder may also need changes depending on how ACLED's data model differs from assumptions.

**WET-before-DRY awareness:** We have two data sources, not three. No shared abstractions should be extracted until a third source (V-Dem?) confirms what is actually common between them. Current similarities between UCDP and ACLED pipelines:

| Component | What looks similar | What's actually different |
|-----------|-------------------|--------------------------|
| Harvester | Config → fetch → validate → store → provenance | ACLED: OAuth2 password grant. UCDP: simple token. ACLED pagination has no TotalCount verification (API doesn't expose one). |
| Consolidator | Read snapshots → tag metadata → deduplicate → write store | UCDP: merges 3 sub-sources with vintage tracking. ACLED: single source, no vintages. |
| Viewpoint | Read store → filter → assign date_month → strip metadata → write | UCDP: survivorship strategies, temporal distribution, source_distribution_map. ACLED: none of these (1:1 event mapping). |

The implicit `HarvestPipeline` template (C-44) now spans 6 sources. Template extraction remains deferred until V-Dem (7th source) or until a real divergence forces the question.

**System snapshot:** 10 packages, 730+ tests, 28 ADRs, 21 CICs. 152 concern IDs tracked: 99 resolved, 45 open/deferred, 6 accepted by design.

---

## Completed Phases

### Phase 0-2c: UCDP Production Parity — COMPLETE
Full pipeline: harvest (5 sources) → consolidate → viewpoint → compile → assemble → export (zarr + parquet). 100% event-level match on 27,853 non-expanded events (.9-only test). Three-source consumer parity at 0.014-0.023% per feature column — residual is annual version difference, not a code defect. See `reports/consumer_parity_investigation.md` and `reports/dot9_investigation/parity_results.md`.

### Phase 2d: Data Serving Infrastructure — COMPLETE
Caddy on Hetzner, basic auth, cron, 10-check verification, consumer guides. See `docs/guides/hetzner_deployment_guide.md`.

### Phase DH-1: v1.0 Deployment Hardening — COMPLETE (2026-04-02)
Export timestamp, main branch current, v1.0.0 tagged, logrotate, e2e integration test.

### Phase DH-2a: v1.1 Code Work — COMPLETE (2026-04-07)
Tag-based deployment gate (ADR-022), freshness SLO (168h, ADR-018), health check tests, atomic assembly writes, version parsing hardening, date format validation, shared adapter validation, timeout policy documented.

### Phase CA-1: Consumer API MVP — COMPLETE (2026-04-08)
`datafactory_query` package with `load_dataset()`, regions, temporal parsing, FeatureFrame/DataFrame output, zarr support, consumer parity tests. Config promotion: `source_distribution_map`, `filter_stale_versions`, `output_dtype`, `fill_value`.

### Phase CA-2a: Verification Examples Suite — COMPLETE (2026-04-21)
15 standalone verification scripts, all passing. Remote zarr smoke test against live Hetzner server passes.

### Phase ACLED-0: ACLED Infrastructure — COMPLETE (2026-05-03)
Built from UCDP patterns and ACLED API documentation:

- Harvester (`datafactory_harvester/sources/acled.py`): OAuth2 password grant, paginated fetch, event validation, Parquet snapshot storage, provenance ledger
- Consolidator (`datafactory_consolidation/consolidators/acled.py`): single-source consolidation, metadata tagging, content-digest deduplication
- Viewpoint builder (`datafactory_viewpoint/builders/acled_v1.py`): event type filtering, `date_month` assignment, metadata stripping
- Profiles: `acled_violence_only` (3 event types), `acled_all_events`
- 62 tests (Green + Beige + Red), 4 CICs, credential setup guide, ADR-027 ACLED pagination note
- **Not validated against real ACLED API.** Infrastructure only.

---

## Active Directions

### Direction 1: Consumer Integration — CURRENT FOCUS

**Problem solved:** The consumer API exists and is verified against the gold set. What remains is proving it works with real training scripts.

**Next steps:**
1. Integrate with first training script (bright_starship) — let friction surface
2. Merge development → main, tag v1.2
3. ADR-026 (query layer architecture) once interface is proven

### Direction 2: ACLED Phase 2 — NEEDS USER INPUT

**Problem:** Phase 0 infrastructure exists but is unvalidated. Phase 2 validates against the real API and either confirms the assumptions or reworks the code.

**What Phase 2 needs from the user:**

| # | Input needed | Why | Priority |
|---|-------------|-----|----------|
| 1 | **ACLED API documentation** — endpoint specs, response envelope format, pagination model, rate limits | Current code assumes UCDP-like `limit`/`offset` pagination and a `data` array in the response. If ACLED uses cursor-based pagination, nested objects, or a different envelope, the harvester needs rework. | Critical |
| 2 | **Old ACLED ingestor script** — the working script from previous research | Shows what the real API actually returns, what edge cases were handled, what the event schema looks like. The current `REQUIRED_FIELDS` and `FIELD_TYPES` are assumptions derived from documentation. | Critical |
| 3 | **API credentials** — `ACLED_USERNAME` and `ACLED_PASSWORD` | Cannot hit the API without them. Set in `~/.profile` per the credential setup guide. | Critical |
| 4 | **A sample API response** — even one real JSON response | Validates whether `fetch_paginated` → `validate_events` → `save_event_snapshot` works or needs restructuring. | High |

**Phase 2 work (after inputs received):**
1. Compare old ingestor against current `acled.py` — identify assumption mismatches
2. Hit real API with credentials — capture actual response envelope
3. Rework harvester if pagination/envelope/schema differs from assumptions
4. Run full pipeline: harvest → consolidate → viewpoint → verify output
5. Update CICs and tests if behavior changes

**What might break:**
- Pagination model (ACLED might use cursors, not `limit`/`offset`)
- Response envelope (might not have a top-level `data` array)
- Event schema (`REQUIRED_FIELDS` and `FIELD_TYPES` are guesses)
- `_assign_date_month` assumes ISO date format — ACLED might use different date formatting
- Count verification: ACLED API has no TotalCount (documented in ADR-027), so silent truncation is possible

### Direction 3: V-Dem — INVESTIGATION

| Source | Type | Resolution | Status | Dependency |
|--------|------|-----------|--------|------------|
| V-Dem | Democracy indicators | Country-year | Investigation | Consumer integration proven |
| WID | Inequality | Country-year | Investigation | Consumer integration proven |

V-Dem would be the **third data source** — the point at which WET-before-DRY allows extracting shared patterns (if any exist). Until then, each source pipeline stays independent.

### Direction 4: Raster Sources — BLOCKED on rasterio

Unchanged. Population, built-up area, nightlights require raster-to-grid aggregation. Blocked on rasterio/GDAL dependency.

### Direction 5: Deployment Hardening — MOSTLY COMPLETE

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

### ACLED (new)

| RQ | Topic | Status |
|----|-------|--------|
| AQ-1 | Does the real ACLED API match our assumed pagination model? | **Blocked** — needs API docs + credentials |
| AQ-2 | Does the ACLED event schema match our REQUIRED_FIELDS? | **Blocked** — needs sample response or old ingestor |
| AQ-3 | Does ACLED coverage predict UCDP violence? (= RQ-8) | Not started |
| AQ-4 | How do UCDP and ACLED event counts compare for overlapping events? (= RQ-10) | Not started |

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
        Phase CA-2a  (verification examples suite — M13, 15 scripts all pass)
        Phase CA-3   (remote zarr smoke test — M12, folded into CA-2a)
        Phase ACLED-0 (ACLED infrastructure — harvester, consolidator, viewpoint, tests, CICs)
        |
NOW:    Phase CA-2b  (first training script integration — M11)
        Phase DH-2b  (v1.1 operator work — blocked on domain + IT)
        |
NEXT:   Merge to main + tag v1.2
        |
THEN:   Phase ACLED-2 (ACLED live API validation — NEEDS USER INPUT)
        Phase 5       (V-Dem integration — third source, enables DRY extraction)
        |
LATER:  Phase DH-3   (v2.0 institutional — OAuth2, audit trail)
        Phase 7      (WID integration — inequality indicators)
        Phase 3      (raster sources — blocked on rasterio)
        Phase 8      (cross-source analysis — AQ-3, AQ-4, RQ-7, RQ-9, RQ-11)
```

---

## Risk Register

Active concerns tracked in `reports/technical_risk_register.md` (ADR-020).

**Current:** 152 concern IDs: 99 resolved, 45 open/deferred, 6 accepted by design.

| Category | Count | Key items |
|----------|-------|-----------|
| Tier 1 | 0 open | All resolved |
| Tier 2 | 7 open | C-88 (SSH), C-130–C-132 (data boundary/monitoring), C-137–C-139 (data integrity), C-149 (GAUL unmapped cells) |
| Tier 3 | 10 open | C-21 (characterization tests), C-126 (transform gap), C-129–C-133 (various), C-144–C-146 (memory/testability) |
| Tier 4 | 22 open | Most untriggered; 2 accepted at v1.0 |
| Accepted | 6 | C-06, C-07, C-10, C-32, C-38, C-41 |

---

## Architecture References

| ADR | Relevance |
|-----|-----------|
| ADR-012 | 4-layer graph architecture |
| ADR-013 | Consolidation: lossless, append-only, bitemporal |
| ADR-014 | Viewpoints: disposable, rebuildable, versioned |
| ADR-015 | UCDP consolidation specifics |
| ADR-016 | Viewpoint profiles (named presets) — applies to UCDP and ACLED |
| ADR-017 | Vintage-aware consolidation (content-digest dedup) |
| ADR-018 | Operational resilience + timeout policy + freshness SLO |
| ADR-020 | Technical risk register |
| ADR-021 | Zarr export format |
| ADR-022 | Tag-based deployment gate |
| ADR-023 | Viewpoint builder invariants (non-configurable decisions) |
| ADR-024 | Compilation grid invariants |
| ADR-026 | Credential management — covers UCDP token + ACLED OAuth2 |
| ADR-027 | Harvest count verification — UCDP has TotalCount, ACLED does not |
