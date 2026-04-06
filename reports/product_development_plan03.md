# Product Development Plan v03 — Deployment Readiness

**Date:** 2026-04-02
**Supersedes:** product_development_plan02.md (2026-03-25)
**Status:** Active
**Goal:** Production-quality data factory serving research consumers with verified operational reliability.

---

## Current State

### What Works

| Layer | Component | Status | Tests |
|-------|-----------|--------|-------|
| 0 | Provenance (digests, ledgers, locking, rotation, schema fingerprint) | Done | 30 |
| 0 | HTTP retry with backoff + jitter (`datafactory_http`) | Done | 7 |
| 1 | PRIO-GRID backbone (grid, temporal, parity, shapefile, land mask) | Done | 67 |
| 1 | Harvester — UCDP annual | Done | 15 |
| 1 | Harvester — UCDP candidate | Done | 16 |
| 1 | Harvester — UCDP .9 | Done | 14 |
| 1 | Harvester — PRIO-GRID static (34 variables) | Done | 13 |
| 1 | Harvester — GAUL admin boundaries (3 levels) | Done | 12 |
| 2 | Consolidation (3-source, vintage-aware, atomic writes) | Done | 35 |
| 3 | Viewpoint (survivorship, distribution, filtering, profiles) | Done | 55 |
| 4 | Grid compilation (columnar placement, feature disaggregation) | Done | 25 |
| — | Adapters (FeatureFrame, grid-to-DataFrame, shape validation) | Done | 35 |
| — | DAG enforcement | Done | 1 |
| — | Integration tests | Done | 4 |
| — | Script structure tests | Done | 10 |
| — | Falsification stubs (UCDP, deployment, netrc) | Done | 15 (marker-gated) |
| — | HTTP serving (Caddy, basic auth, cron) | Done | 0 (operational) |
| — | Consumer verification (`verify_remote.py`) | Done | 0 (script) |

**Total: 411 passed**

### Architecture

- **9 packages** under `src/datafactory_*`: provenance, http, priogrid, harvester, synthetic (stub), consolidation, viewpoint, compilation, adapters
- **5 data sources**: UCDP annual, UCDP candidate, UCDP .9, PRIO-GRID static, GAUL admin boundaries
- **22 ADRs** (10 constitutional + 12 project-specific)
- **16 CICs** (class intent contracts)
- **Technical risk register** (ADR-020): 111 concern IDs tracked, 72 resolved, 31 open/deferred, 6 accepted by design

### Production Parity — ALL CRITERIA MET (2026-03-21)

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Harvest all three UCDP streams | MET | annual, candidate, .9 harvesters |
| Consolidated store with vintage tracking | MET | ADR-017 dedup, schema fingerprint |
| <5% event-level discrepancy | EXCEEDED | 100% match on 27,853 non-expanded events |
| All discrepancies documented | MET | `reports/dot9_investigation/parity_results.md` |
| Full pipeline end-to-end | MET | harvest -> consolidate -> viewpoint -> compile -> assemble |

---

## Milestones

| Milestone | Description | Status |
|-----------|-------------|--------|
| M1 | .9 harvester | Complete |
| M2 | Three-source consolidation | Complete |
| M3 | .9-aware survivorship (`dot9_wins`) | Complete |
| M4 | Production-parity summary handling (`ceil_split`) | Complete |
| M5 | Production filtering rules | Complete |
| M6 | End-to-end production parity test | Complete |
| M7 | Data serving operational (Caddy + cron + auth) | Complete |
| **M8** | **Deployment quality v1.0 (single-user gate)** | **Open** |
| M9 | Multi-user readiness v1.1 | Not started |

---

## Operational Readiness

### What Has Been Achieved

- Caddy 2.11.2 file server on Hetzner (CPX32, Helsinki, 204.168.219.108)
- HTTP port 80 with basic auth (username: `views`, bcrypt hash in Caddyfile)
- Consumer credentials via `~/.netrc` + `aiohttp.BasicAuth` wrapper for xarray
- `verify_remote.py` — 10 automated checks (connectivity, auth, metadata, dimensions, variables, data access, sanity, parquet)
- Cron: pipeline runs 21st of each month at midnight UTC
- Failure notification: `logs/pipeline_failure.json` sentinel + optional `ALERT_EMAIL`
- `check_health.py` reports staleness and recent failures
- Consumer guides: zarr + pandas examples in deployment guide
- Deployment log: 15 lessons from 10 deployment incidents

### Falsification Findings (2026-04-01)

A falsification audit tested the claim "we are at deployment quality."
Verdict: **FALSIFIED** (1 hard, 3 soft, 1 observation).

| ID | Severity | Title | Risk ref | Blocks |
|----|----------|-------|----------|--------|
| F1 | **Hard** | No freshness indicator in zarr/parquet exports | D-03 (Tier 1) | v1.0 |
| F2 | Soft | Development 35 commits ahead of main; server runs development | — | v1.0 |
| F3 | Soft | HTTP not HTTPS — credentials in cleartext on wire | — | v1.1 |
| F4 | Observation | No log rotation (11 KB/month, years until problem) | — | v1.0 |
| F5 | Soft | No deployment gate between push and server | — | v1.1 |

### Deferred Items Now Triggered

| ID | Tier | Title | Trigger condition | Blocks |
|----|------|-------|-------------------|--------|
| D-03 | 1 | Fail-loud vs. operational resilience (freshness gap) | Before production deployment | v1.0 |
| C-29 | 4 | No end-to-end integration test | Before production deployment | v1.0 |
| C-88 | 2 | SSH not restricted to PRIO/Uppsala IPs | Before production deployment | v1.1 |
| C-84 | 2 | Server runs everything as root | Before second user access | v1.1 |
| C-85 | 2 | Personal GitHub SSH key on shared server | Before second user access | v1.1 |
| C-86 | 2 | No deploy key — repo access tied to personal account | Before second user access | v1.1 |
| C-87 | 2 | No named user accounts on server | Before second user access | v1.1 |
| C-89 | 4 | No formal SLO for data freshness | Before second consumer | v1.1 |

### Accepted / Contested Items

| ID | Title | Resolution |
|----|-------|------------|
| C-96 | fsspec does not auto-read `~/.netrc` | Accepted: 3-line `aiohttp.BasicAuth` wrapper in consumer guide. Revisit if fsspec adds netrc/trust_env support. |
| C-97 | Basic auth + Caddy ceiling at 30-50 users | Accepted for v1.0-v1.1. Migrate to OAuth2 (`forward_auth` + oauth2-proxy) for v2.0. |

---

## Definition of Deployment Quality

Three versioned tiers with explicit gate criteria.

### v1.0 — Single-user research deployment

The primary researcher can rely on the system for daily work.

| Criterion | How to verify |
|-----------|--------------|
| No open Tier 1 items in risk register | `test_falsification_deployment.py::test_tier1_items_resolved` passes |
| `main` branch is current | development merged, `main..development` is 0 commits |
| Semantic version tag exists | `git tag -l` shows v1.0.0 |
| `export_timestamp` in zarr attrs | `verify_remote.py` check 5 includes timestamp |
| Log rotation configured | `/etc/logrotate.d/views-datafactory` exists on server |
| E2e integration test exists | `test_integration.py` covers 3-source mini-pipeline |
| `test_falsification_deployment.py` passes | Both tests green |

### v1.1 — Multi-user / external consumers

5-20 research consumers can be onboarded and use the data safely.

| Criterion | How to verify |
|-----------|--------------|
| All v1.0 criteria | — |
| HTTPS with valid TLS certificate | `curl https://data.views.uu.se/` returns 200 with valid cert |
| Deployment uses tag checkout | `refresh_pipeline.sh` checks out git tag, not branch tip |
| SSH restricted to institutional IPs | Hetzner firewall rules configured |
| Non-root service account | `ps -u views-deploy` shows pipeline process |
| Deploy key for GitHub | `/root/.ssh/` has deploy key, not personal key |
| Named server accounts | `getent passwd simon colleague-name` exists |
| Freshness SLO defined | zarr `export_timestamp` checked by consumer / monitoring |

### v2.0 — Institutional / scaled deployment

Meets institutional audit and compliance requirements for 50+ users.

| Criterion | How to verify |
|-----------|--------------|
| All v1.1 criteria | — |
| OAuth2 / institutional SSO | Caddy `forward_auth` + oauth2-proxy configured |
| Per-user audit trail | Access logs with authenticated username |
| Circuit breaker on APIs | `datafactory_http` circuit breaker module |
| Pipeline duration tracked | Provenance ledger includes `duration_seconds` |

---

## Prioritized Action List

| Priority | Task | Effort | Finding/Ref | Target |
|----------|------|--------|-------------|--------|
| 1 | Add `export_timestamp` to zarr attrs in `export_zarr.py` | 1h | F1, D-03 | v1.0 |
| 2 | Merge development to main | 1h | F2 | v1.0 |
| 3 | Establish tagging convention, tag v1.0.0 | 30m | F2 | v1.0 |
| 4 | Add e2e integration test (3-source mini-pipeline) | 2h | C-29 | v1.0 |
| 5 | Add logrotate config on server | 30m | F4 | v1.0 |
| 6 | Register domain, point DNS to Hetzner | 1-2d | F3 | v1.1 |
| 7 | Swap Caddyfile to domain block (auto-TLS) | 30m | F3 | v1.1 |
| 8 | Tag-based deployment gate in `refresh_pipeline.sh` | 2h | F5 | v1.1 |
| 9 | Restrict SSH to PRIO/Uppsala IPs | 1h | C-88 | v1.1 |
| 10 | Create `views-deploy` non-root service account | 2h | C-84 | v1.1 |
| 11 | Replace personal SSH key with deploy key + named accounts | 2h | C-85/86/87 | v1.1 |
| 12 | Define measurable freshness SLO | 2h | C-89 | v1.1 |
| 13 | Migrate to OAuth2 (forward_auth + oauth2-proxy) | 1-2w | C-97 | v2.0 |
| 14 | Per-user audit trail | 1w | C-97 | v2.0 |
| 15 | Circuit breaker for upstream APIs | 1d | C-70 | v2.0 |
| 16 | Pipeline duration tracking | 4h | C-91 | v2.0 |

**Total effort to v1.0:** ~5 hours
**Total effort to v1.1:** ~2-3 additional days (dominated by domain registration)
**Total effort to v2.0:** ~3-4 additional weeks

---

## Operational Concerns (Summary)

- **Tier 1:** 0 open — D-03 resolved (export_timestamp + ADR-018)
- **Tier 2:** 5 open (C-84 through C-88) — all resolved by v1.1 tasks
- **Tier 3:** 2 open (C-21 characterization tests, C-102 assembly/export tests)
- **Tier 4:** 28 open — most not yet triggered; 2 triggered and accepted at v1.0 (C-29, C-44)
- **Accepted by design:** C-06, C-07, C-10, C-38, C-41

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
| ADR-018 | Operational resilience policy |
| ADR-019 | Visualization style guide |
| ADR-020 | Technical risk register |
