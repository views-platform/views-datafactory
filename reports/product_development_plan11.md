# Product Development Plan v11 — v1.2 Complete, ACLED Proven on Server

**Date:** 2026-05-08
**Supersedes:** product_development_plan10.md (2026-05-06)
**Status:** Active
**Goal:** A data factory that training scripts can depend on — robust subsetting, multiple output formats, verified parity, multiple conflict data sources.

---

## Current State

### What Works

| Layer | Component | Status | Tests |
|-------|-----------|--------|-------|
| 0 | Provenance (digests, ledgers, locking, rotation, schema fingerprint, health diagnostics) | Done | 47 |
| 0 | HTTP retry with backoff + jitter (`datafactory_http`) | Done | 7 |
| 1 | PRIO-GRID backbone (grid, temporal, parity, shapefile, land mask) | Done | 67 |
| 1 | Harvester — UCDP annual | Done | 15 |
| 1 | Harvester — UCDP candidate | Done | 16 |
| 1 | Harvester — UCDP .9 | Done | 14 |
| 1 | Harvester — PRIO-GRID static (34 variables) | Done | 13 |
| 1 | Harvester — GAUL admin boundaries (3 levels) | Done | 12 |
| 1 | Harvester — ACLED (OAuth2, paginated, year-by-year, courteous) | Done (server-proven) | 46 |
| 2 | Consolidation — UCDP (3-source, vintage-aware, atomic writes) | Done | 35 |
| 2 | Consolidation — ACLED (single-source, metadata tagging) | Done (server-proven) | 13 |
| 3 | Viewpoint — UCDP (survivorship, distribution, filtering, profiles) | Done | 85 |
| 3 | Viewpoint — ACLED (event type filter, date_month, profiles) | Done (server-proven) | 20 |
| 4 | Grid compilation — UCDP (columnar placement, feature disaggregation, configurable dtype/fill) | Done | 39 |
| 4 | Grid compilation — ACLED (8 features, column projection, OOM-safe) | Done (server-proven) | 11 |
| — | Assembly (UCDP + ACLED + static + admin → 51 features) | Done (server-proven) | 24 |
| — | Adapters (FeatureFrame, grid-to-DataFrame, shared validation) | Done | 39 |
| — | Query (regions, temporal parsing, unified load_dataset, zarr support) | Done | 34 |
| — | Consumer parity (DataFrame, FeatureFrame, zarr vs VIEWSER gold set) | Done | 3 (marker-gated) |
| — | DAG enforcement | Done | 1 |
| — | Integration tests | Done | 4 |
| — | Script structure tests | Done | 10 |
| — | Health check tests | Done | 17 |
| — | Falsification stubs (UCDP, deployment, netrc, ACLED) | Done | 17 (marker-gated) |
| — | HTTP serving (Caddy, basic auth, cron) | Done | 0 (operational) |
| — | Verification examples (`examples/run_examples.sh`) | Done | 15 scripts |
| — | Falsification stubs (viewser replacement claim) | Done | 7 (marker-gated) |
| — | ACLED grid verification (13 plots, 8 checks) | Done | 0 (script) |
| — | Remote verification (10-check server probe) | Done | 0 (script) |

**Total: ~821 tests (pytest) + 15 verification examples + 10-check remote verification**

**Status key:**
- **Done** = code exists, tested, validated against real data
- **Done (server-proven)** = code exists, tested, and confirmed working end-to-end on the production Hetzner server

### Architecture

- **10 packages** under `src/datafactory_*`: provenance, http, priogrid, harvester, synthetic (stub), consolidation, viewpoint, compilation, adapters, query
- **6 data sources**: UCDP annual, UCDP candidate, UCDP .9, PRIO-GRID static, GAUL admin boundaries, ACLED
- **29 ADRs** (10 constitutional + 19 project-specific)
- **21 CICs** (class intent contracts)
- **Technical risk register** (ADR-020): 160 concern IDs tracked, 104 resolved, 46 open/deferred, 6 accepted by design
- **Deployed:** v1.2.14 on Hetzner, serving 51 features via zarr + parquet

### WET-before-DRY Status

Two data source pipelines exist (UCDP, ACLED). They look similar but have real structural differences:

- **Harvesters:** ACLED uses OAuth2 password grant; UCDP uses a simple API token. ACLED has no TotalCount verification.
- **Consolidators:** UCDP merges 3 sub-sources with vintage tracking (ADR-017); ACLED merges one source with no vintages.
- **Viewpoints:** UCDP has survivorship strategies, temporal distribution, and `source_distribution_map`; ACLED has none.
- **Compilers:** Same `FeatureSpec` pattern (ADR-024) but different feature sets and spatial assignment logic.

**Rule:** No shared abstractions until a third source (V-Dem or WDI) confirms what is genuinely common.

---

## Milestones

| Milestone | Description | Status |
|-----------|-------------|--------|
| M1-M9 | UCDP parity + deployment | Complete |
| M10/M10a | Consumer API + parity investigation | Complete |
| M13 | Verification examples suite | Complete (2026-04-21) |
| M12 | Remote zarr smoke test | Complete (2026-04-21) |
| M14 | ACLED Phase 0 infrastructure | Complete (2026-05-03) |
| M15 | ACLED Phase 2 — real API validation | Complete (2026-05-05) |
| M16 | ACLED compilation design decisions | Complete (2026-05-05) |
| M17 | ACLED compilation — build the compiler | Complete (2026-05-06) |
| M11 | Training script integration | Complete (2026-05-06) |
| M19 | ACLED grid verification — 13 plots, 8 checks | Complete (2026-05-06) |
| M18 | ACLED assembly integration | **Complete (2026-05-07)** |
| M20 | Courteous harvesting + test review | **Complete (2026-05-07)** |
| M21 | OOM fix + server deployment (v1.2.14) | **Complete (2026-05-08)** |
| M22 | Remote verification — 10/10 checks pass | **Complete (2026-05-08)** |

---

## Definition of Deployment Quality

### v1.0 — Single-user research deployment — COMPLETE
### v1.1 — Multi-user / external consumers — CODE COMPLETE (operator work blocked)

### v1.2 — Consumer API + ACLED — COMPLETE

| Criterion | How to verify | Status |
|-----------|--------------|--------|
| All v1.1 code criteria | — | **Done** |
| `load_dataset()` works on full grid | Consumer parity tests (~30s) | **Done** |
| Consumer parity tests pass | 3 tests vs gold set | **Done** |
| Verification examples pass | `bash examples/run_examples.sh` exits 0 | **Done** |
| First consumer integrated | Training scripts run end-to-end | **Done** |
| ACLED harvester validated | Real API, 46 tests pass | **Done** |
| ACLED compilation built | 8 features, end-to-end pipeline | **Done** |
| ACLED grid verified | 13 plots + 8 statistical checks pass | **Done** |
| ACLED in assembled grid | `load_dataset()` exposes ACLED features | **Done** |
| Full pipeline proven on server | All 12 sources healthy, 10-check remote verification | **Done** |

### v2.0 — Institutional / scaled deployment

| Criterion | How to verify |
|-----------|--------------|
| All v1.2 criteria | — |
| Third data source integrated | V-Dem or WDI compiled + assembled + served |
| OAuth2 / institutional SSO | Caddy `forward_auth` + oauth2-proxy |
| Per-user audit trail | Access logs with authenticated username |
| Circuit breaker on APIs | `datafactory_http` circuit breaker module |
| Pipeline duration tracked | Provenance ledger includes `duration_seconds` |

---

## Prioritized Action List

### Completed

| # | Task | Ref | Date |
|---|------|-----|------|
| 1-13 | UCDP parity + consumer API + config promotion | — | Through 2026-04-08 |
| 14a | Verification examples suite | M13 | 2026-04-21 |
| 15 | Remote zarr smoke test | M12 | 2026-04-21 |
| 25a | ACLED Phase 0 infrastructure | M14 | 2026-05-03 |
| 25b | ACLED test review findings | C-150/151/152 | 2026-05-03 |
| 25c | ACLED documentation alignment | review-base-docs | 2026-05-03 |
| 25d | ACLED Phase 2 — real API validation | M15 | 2026-05-05 |
| 25e | ACLED compilation design decisions | M16, ADR-028 | 2026-05-05 |
| 25f | ACLED compilation — build the compiler | M17 | 2026-05-06 |
| 14 | Training script integration | M11 | 2026-05-06 |
| 25g | ACLED grid verification — 13 plots, 8 checks | M19 | 2026-05-06 |
| 25h | ACLED assembly integration | M18 | 2026-05-07 |
| 25i | Courteous harvesting + test review | M20 | 2026-05-07 |
| 25j | OOM fix (column projection) + server deploy v1.2.14 | M21 | 2026-05-08 |
| 25k | Remote verification — 10/10 checks pass | M22 | 2026-05-08 |

### Active

| # | Task | Effort | Ref | Status |
|---|------|--------|-----|--------|
| 27 | Choose next source (V-Dem vs WDI) | Decision | — | Ready |
| 28 | Third source: harvester + consolidation + viewpoint + compilation | ~1 week | Direction 1 | After #27 |

### Blocked (v1.1 operator work)

| # | Task | Blocker |
|---|------|---------|
| 17 | Register domain + HTTPS | Domain not registered |
| 18 | Restrict SSH to institutional IPs | IT CIDRs not provided |
| 19 | Service account + deploy key | Requires SSH to server |

### Deferred (v2.0)

| # | Task | Ref | Target |
|---|------|-----|--------|
| 20 | OAuth2 (forward_auth + oauth2-proxy) | C-97 | v2.0 |
| 21 | Per-user audit trail | C-97 | v2.0 |
| 22 | Circuit breaker for APIs | C-70 | v2.0 |
| 23 | Pipeline duration tracking | C-91 | v2.0 |

### Deferred (source expansion)

| # | Task | Ref | Depends on |
|---|------|-----|------------|
| 24 | V-Dem harvester + full pipeline | Direction 1 | Decision #27 |
| 26 | WDI harvester + full pipeline | Direction 1 | Decision #27 |

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
