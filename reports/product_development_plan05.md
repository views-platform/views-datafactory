# Product Development Plan v06 — Verification Suite

**Date:** 2026-04-21
**Supersedes:** product_development_plan05.md (2026-04-08)
**Status:** Active
**Goal:** A data factory that training scripts can depend on — robust subsetting, multiple output formats, verified parity.

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
| 2 | Consolidation (3-source, vintage-aware, atomic writes) | Done | 35 |
| 3 | Viewpoint (survivorship, distribution, filtering, profiles, source_distribution_map) | Done | 85 |
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
| — | Consumer verification (`verify_remote.py`) | Done | 0 (script) |
| — | Verification examples (`examples/run_examples.sh`) | Done | 15 scripts (12 pass, 2 xfail, 1 remote) |
| — | Falsification stubs (viewser replacement claim) | Done | 7 (marker-gated) |

**Total: 636 passed (pytest) + 15 verification examples**

### Architecture

- **10 packages** under `src/datafactory_*`: provenance, http, priogrid, harvester, synthetic (stub), consolidation, viewpoint, compilation, adapters, query
- **5 data sources**: UCDP annual, UCDP candidate, UCDP .9, PRIO-GRID static, GAUL admin boundaries
- **30 ADRs** (10 constitutional + 20 project-specific)
- **19 CICs** (class intent contracts)
- **Technical risk register** (ADR-020): 143 concern IDs tracked, 96 resolved, 39 open/deferred, 6 accepted by design

---

## Milestones

| Milestone | Description | Status |
|-----------|-------------|--------|
| M1 | .9 harvester | Complete |
| M2 | Three-source consolidation | Complete |
| M3 | .9-aware survivorship (`dot9_wins`) | Complete |
| M4 | Production-parity summary handling (`source_distribution_map` — annual: date_end_only, .9: ceil_split) | Complete |
| M5 | Production filtering rules | Complete |
| M6 | End-to-end production parity test | Complete |
| M7 | Data serving operational (Caddy + cron + auth) | Complete |
| M8 | Deployment quality v1.0 (single-user gate) | Complete (2026-04-02, tag v1.0.0) |
| M9 | Multi-user readiness v1.1 (code work) | Complete (2026-04-07, tag v1.1.0; operator work blocked) |
| M10 | Consumer API MVP (`datafactory_query`) | Complete (2026-04-08) |
| M10a | Consumer parity investigation — source_aware distribution + config promotion | Complete (2026-04-08) |
| M13 | Verification examples suite — every API capability demonstrated | Complete (2026-04-21) |
| **M11** | **First training script integration** | **Not started** |
| M12 | Remote data access (zarr path smoke test) | Complete (2026-04-21, via `ex_zarr_remote.py`) |

---

## Definition of Deployment Quality

### v1.0 — Single-user research deployment — COMPLETE

| Criterion | Status |
|-----------|--------|
| No open Tier 1 items | **Done** |
| `main` branch current | **Done** |
| Semantic version tag (v1.0.0) | **Done** |
| `export_timestamp` in zarr attrs | **Done** |
| Log rotation configured | **Done** |
| E2e integration test | **Done** |
| `test_falsification_deployment.py` passes | **Done** |

### v1.1 — Multi-user / external consumers — CODE COMPLETE

| Criterion | Status |
|-----------|--------|
| All v1.0 criteria | **Done** |
| HTTPS with valid TLS certificate | Blocked on domain |
| Deployment uses tag checkout | **Done** (ADR-022) |
| SSH restricted to institutional IPs | Blocked on IT CIDRs |
| Non-root service account | Procedure documented |
| Deploy key for GitHub | Procedure documented |
| Named server accounts | Procedure documented |
| Freshness SLO defined | **Done** (168h, ADR-018) |

### v1.2 — Consumer API — IN PROGRESS

A training script can pull the data it needs without hacks.

| Criterion | How to verify | Status |
|-----------|--------------|--------|
| All v1.1 code criteria | — | **Done** |
| `load_dataset()` works on full grid | Consumer parity tests (~30s) | **Done** |
| Region definitions validated | Parity tests cover 13,110 VIEWSER pgids | **Done** |
| Consumer parity tests pass | 3 tests vs gold set | **Done** (0.014-0.023% residual) |
| Viewpoint choices configurable | `source_distribution_map`, `filter_stale_versions` | **Done** |
| Remote/zarr path in `load_dataset()` | `load_dataset(data_dir="http://...")` | **Done** (M12, `ex_zarr_remote.py` passes) |
| Verification examples pass | `bash examples/run_examples.sh` exits 0 | **Done** (M13, 15 scripts) |
| First consumer integrated | Training script runs end-to-end | **Not started** |

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

| # | Task | Finding/Ref | Target | Date |
|---|------|-------------|--------|------|
| 1 | Add `export_timestamp` to zarr attrs | F1, D-03 | v1.0 | 2026-04-02 |
| 2 | Merge development to main | F2 | v1.0 | 2026-04-02 |
| 3 | Tag v1.0.0 | F2 | v1.0 | 2026-04-02 |
| 4 | E2e integration test | C-29 | v1.0 | 2026-04-02 |
| 5 | Logrotate on server | F4 | v1.0 | 2026-03-31 |
| 6 | Tag-based deployment gate | F5, C-98 | v1.1 | 2026-04-06 |
| 7 | Freshness SLO | C-89 | v1.1 | 2026-04-06 |
| 8 | Tech debt cleanup | C-112, C-113 | — | 2026-04-06 |
| 9 | Tier 4 production hardening | C-60, C-104-C-106 | — | 2026-04-07 |
| 10 | Health check → provenance.health | — | — | 2026-04-07 |
| 11 | Consumer API MVP (datafactory_query) | — | v1.2 | 2026-04-07 |
| 12 | Consumer parity investigation + source_distribution_map | RQ-4 | v1.2 | 2026-04-08 |
| 13 | Config promotion (viewpoint + compilation) | ADR-023, 024 | v1.2 | 2026-04-08 |

### Active

| # | Task | Effort | Ref | Target | Status |
|---|------|--------|-----|--------|--------|
| 14a | Verification examples suite | 1d | M13 | v1.2 | Complete (2026-04-21) |
| 14 | First training script integration | 1-2d | CQ-4 | v1.2 | Not started |
| 15 | Remote zarr smoke test on live server | 2h | CQ-3 | v1.2 | Complete (via M13 `ex_zarr_remote.py`) |
| 16 | Merge development → main + tag v1.2 | 1h | — | v1.2 | After M11 |

### Blocked (v1.1 operator work)

| # | Task | Effort | Ref | Blocker |
|---|------|--------|-----|---------|
| 17 | Register domain + HTTPS | 1-2d | F3 | Domain not registered |
| 18 | Restrict SSH to institutional IPs | 1h | C-88 | IT CIDRs not provided |
| 19 | Service account + deploy key | 4h | C-84-C-87 | Requires SSH to server |

### Deferred (v2.0)

| # | Task | Effort | Ref | Target |
|---|------|--------|-----|--------|
| 20 | OAuth2 (forward_auth + oauth2-proxy) | 1-2w | C-97 | v2.0 |
| 21 | Per-user audit trail | 1w | C-97 | v2.0 |
| 22 | Circuit breaker for APIs | 1d | C-70 | v2.0 |
| 23 | Pipeline duration tracking | 4h | C-91 | v2.0 |

### Deferred (source expansion)

| # | Task | Effort | Ref | Depends on |
|---|------|--------|-----|------------|
| 24 | V-Dem harvester + consolidation | 1-2w | Direction 2 | Consumer integration proven |
| 25 | ACLED harvester + consolidation | 2-3w | Direction 2 | Consumer integration proven + access |
| 26 | WID harvester + consolidation | 2-3w | Direction 2 | Consumer integration proven |

---

## Operational Concerns (Summary)

- **Tier 1:** 0 open
- **Tier 2:** 5 open (C-84-C-88) — server hardening, blocked on external
- **Tier 3:** 1 open (C-21) — characterization tests, untriggered
- **Tier 4:** 15 open — most untriggered; 2 accepted at v1.0 (C-29, C-44); C-115 new (summary threshold)
- **Accepted by design:** C-06, C-07, C-10, C-32, C-38, C-41

---

## Architecture References

| ADR | Relevance |
|-----|-----------|
| ADR-012 | 4-layer graph architecture |
| ADR-013 | Consolidation: lossless, append-only, bitemporal |
| ADR-014 | Viewpoints: disposable, rebuildable, versioned |
| ADR-015 | UCDP consolidation specifics |
| ADR-016 | Viewpoint profiles (named presets) |
| ADR-017 | Vintage-aware consolidation (content-digest dedup) |
| ADR-018 | Operational resilience + timeout policy + freshness SLO |
| ADR-020 | Technical risk register |
| ADR-021 | Zarr export format |
| ADR-022 | Tag-based deployment gate |
| ADR-023 | Viewpoint builder invariants (non-configurable decisions) |
| ADR-024 | Compilation grid invariants |
