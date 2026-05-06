# Product Development Plan v08 — ACLED Phase 0 Complete

**Date:** 2026-05-03
**Supersedes:** product_development_plan06.md (2026-04-21)
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
| 1 | Harvester — ACLED (OAuth2, paginated, event validation) | Done (unvalidated) | 29 |
| 2 | Consolidation — UCDP (3-source, vintage-aware, atomic writes) | Done | 35 |
| 2 | Consolidation — ACLED (single-source, metadata tagging) | Done (unvalidated) | 13 |
| 3 | Viewpoint — UCDP (survivorship, distribution, filtering, profiles) | Done | 85 |
| 3 | Viewpoint — ACLED (event type filter, date_month, profiles) | Done (unvalidated) | 20 |
| 4 | Grid compilation (columnar placement, feature disaggregation, configurable dtype/fill) | Done | 39 |
| — | Adapters (FeatureFrame, grid-to-DataFrame, shared validation) | Done | 39 |
| — | Query (regions, temporal parsing, unified load_dataset, zarr support) | Done | 34 |
| — | Consumer parity (DataFrame, FeatureFrame, zarr vs VIEWSER gold set) | Done | 3 (marker-gated) |
| — | DAG enforcement | Done | 1 |
| — | Integration tests | Done | 4 |
| — | Script structure tests | Done | 10 |
| — | Assembly + export tests | Done | 24 |
| — | Health check tests | Done | 17 |
| — | Falsification stubs (UCDP, deployment, netrc) | Done | 15 (marker-gated) |
| — | HTTP serving (Caddy, basic auth, cron) | Done | 0 (operational) |
| — | Verification examples (`examples/run_examples.sh`) | Done | 15 scripts |
| — | Falsification stubs (viewser replacement claim) | Done | 7 (marker-gated) |

**Total: 730+ passed (pytest) + 15 verification examples**

**"Done (unvalidated)"** means the code exists, has full test coverage (Green + Beige + Red), has a CIC, and follows established patterns — but has never processed real ACLED API data. The tests use synthetic data and mocked API responses.

### Architecture

- **10 packages** under `src/datafactory_*`: provenance, http, priogrid, harvester, synthetic (stub), consolidation, viewpoint, compilation, adapters, query
- **6 data sources**: UCDP annual, UCDP candidate, UCDP .9, PRIO-GRID static, GAUL admin boundaries, ACLED (unvalidated)
- **28 ADRs** (10 constitutional + 18 project-specific)
- **21 CICs** (class intent contracts)
- **Technical risk register** (ADR-020): 152 concern IDs tracked, 99 resolved, 45 open/deferred, 6 accepted by design

### WET-before-DRY Status

Two data source pipelines exist (UCDP, ACLED). They look similar but have real structural differences:

- **Harvesters:** ACLED uses OAuth2 password grant; UCDP uses a simple API token. ACLED has no TotalCount verification.
- **Consolidators:** UCDP merges 3 sub-sources with vintage tracking (ADR-017); ACLED merges one source with no vintages.
- **Viewpoints:** UCDP has survivorship strategies, temporal distribution, and `source_distribution_map`; ACLED has none.

**Rule:** No shared `BaseHarvester`, `BaseConsolidator`, or similar abstraction until a third source (V-Dem) confirms what is genuinely common. C-44 (implicit harvest template) is accepted at v1.0 scope.

---

## Milestones

| Milestone | Description | Status |
|-----------|-------------|--------|
| M1–M9 | UCDP parity + deployment | Complete |
| M10/M10a | Consumer API + parity investigation | Complete |
| M13 | Verification examples suite | Complete (2026-04-21) |
| M12 | Remote zarr smoke test | Complete (2026-04-21) |
| M14 | ACLED Phase 0 infrastructure | **Complete (2026-05-03)** |
| **M11** | **First training script integration** | **Not started** |
| **M15** | **ACLED Phase 2 — real API validation** | **Blocked on user input** |

---

## ACLED Phase 2: What's Needed

Phase 0 built the plumbing. Phase 2 fills it with real water. **Four inputs required from the user:**

### 1. ACLED API documentation (Critical)

The actual endpoint specs, response envelope format, pagination model, and rate limits. The current harvester assumes:
- `limit`/`offset` pagination (like UCDP)
- A top-level `data` array in the JSON response
- Event fields matching `REQUIRED_FIELDS` in `acled.py`

If any of these assumptions are wrong, the harvester needs rework. The consolidator and viewpoint may also need changes.

### 2. Old ACLED ingestor script (Critical)

The working script from previous research. This is the most valuable input because it shows:
- What the real API actually returns (response structure, field names, data types)
- What edge cases were already handled
- What the actual event schema looks like

The current `REQUIRED_FIELDS` and `FIELD_TYPES` are assumptions derived from documentation, not from observed data.

### 3. API credentials (Critical)

`ACLED_USERNAME` and `ACLED_PASSWORD` set in `~/.profile`. The credential setup guide (`docs/guides/credential_setup.md`) documents the procedure. Cannot hit the API without these.

### 4. A sample API response (High)

Even one real JSON response from the ACLED API would validate whether `fetch_paginated` → `validate_events` → `save_event_snapshot` works end-to-end or needs restructuring.

### What might break against real data

| Assumption | Risk | Impact if wrong |
|-----------|------|-----------------|
| `limit`/`offset` pagination | ACLED might use cursor-based pagination | Harvester `fetch_paginated` needs rewrite |
| Top-level `data` array in response | Different envelope structure | Response parsing needs rework |
| `REQUIRED_FIELDS` match real schema | Fields may be named differently or missing | Validation and consolidation need rework |
| ISO date format in `event_date` | ACLED might use different date formatting | `_assign_date_month` silently corrupts (documented in C-150 Red tests) |
| No TotalCount in API response | Confirmed by ADR-027 | Silent truncation possible; no fix without API support |

---

## Definition of Deployment Quality

### v1.0 — Single-user research deployment — COMPLETE
### v1.1 — Multi-user / external consumers — CODE COMPLETE (operator work blocked)

### v1.2 — Consumer API — IN PROGRESS

| Criterion | How to verify | Status |
|-----------|--------------|--------|
| All v1.1 code criteria | — | **Done** |
| `load_dataset()` works on full grid | Consumer parity tests (~30s) | **Done** |
| Consumer parity tests pass | 3 tests vs gold set | **Done** |
| Verification examples pass | `bash examples/run_examples.sh` exits 0 | **Done** |
| First consumer integrated | Training script runs end-to-end | **Not started** |
| ACLED infrastructure tested | 62 tests (Green + Beige + Red) pass | **Done** |
| ACLED validated against real API | Full pipeline with real data | **Blocked on user input** |

### v2.0 — Institutional / scaled deployment

| Criterion | How to verify |
|-----------|--------------|
| All v1.2 criteria | — |
| OAuth2 / institutional SSO | Caddy `forward_auth` + oauth2-proxy |
| Per-user audit trail | Access logs with authenticated username |
| Circuit breaker on APIs | `datafactory_http` circuit breaker module |
| Pipeline duration tracked | Provenance ledger includes `duration_seconds` |

---

## Prioritized Action List

### Completed

| # | Task | Ref | Date |
|---|------|-----|------|
| 1–13 | UCDP parity + consumer API + config promotion | — | Through 2026-04-08 |
| 14a | Verification examples suite | M13 | 2026-04-21 |
| 15 | Remote zarr smoke test | M12 | 2026-04-21 |
| 25a | ACLED Phase 0 infrastructure (harvester + consolidator + viewpoint) | M14 | 2026-05-02 |
| 25b | ACLED test review findings (Red tests + CICs + profiles) | C-150/151/152 | 2026-05-03 |
| 25c | ACLED documentation alignment (credential guide, logging standard, ADR-027, CIC README) | review-base-docs | 2026-05-03 |

### Active

| # | Task | Effort | Ref | Status |
|---|------|--------|-----|--------|
| 14 | First training script integration | 1-2d | M11 | Not started |
| 16 | Merge development → main + tag v1.2 | 1h | — | After M11 |
| 25d | ACLED Phase 2 — real API validation | 1-2w | M15 | **Blocked on user input** |

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
| 24 | V-Dem harvester + consolidation | Direction 3 | Consumer integration proven |
| 26 | WID harvester + consolidation | Direction 3 | Consumer integration proven |

---

## Operational Concerns (Summary)

- **Tier 1:** 0 open
- **Tier 2:** 7 open — server hardening (C-88), data boundary/monitoring (C-130-C-132), data integrity (C-137-C-139), GAUL unmapped (C-149)
- **Tier 3:** 10 open — characterization tests (C-21), transform gap (C-126), memory concerns (C-144-C-145), testability (C-146)
- **Tier 4:** 22 open — most untriggered; 2 accepted at v1.0 (C-29, C-44)
- **Accepted by design:** C-06, C-07, C-10, C-32, C-38, C-41

---

## Architecture References

| ADR | Relevance |
|-----|-----------|
| ADR-012 | 4-layer graph architecture |
| ADR-013 | Consolidation: lossless, append-only, bitemporal |
| ADR-014 | Viewpoints: disposable, rebuildable, versioned |
| ADR-015 | UCDP consolidation specifics |
| ADR-016 | Viewpoint profiles — constitutional, applies to all sources |
| ADR-017 | Vintage-aware consolidation (content-digest dedup) |
| ADR-026 | Credential management — UCDP token + ACLED OAuth2 |
| ADR-027 | Harvest count verification — ACLED has no TotalCount |
