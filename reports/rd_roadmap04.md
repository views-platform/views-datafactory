# R&D Roadmap v04 — Deployment Hardening

**Date:** 2026-04-02
**Supersedes:** rd_roadmap03.md (2026-03-26)
**Status:** Active

---

## Where We Are

The data factory is feature-complete for UCDP conflict data and
operationally serving data from Hetzner. Five data sources, 4-layer
pipeline, production parity achieved. Data served via Caddy over
HTTP with basic auth. Cron runs the pipeline on the 21st of every
month. Consumer verification script (`verify_remote.py`) confirms
10/10 checks pass.

A falsification audit (`test_falsification_deployment.py`, 2026-04-01)
found the system **works end-to-end but is not at deployment quality:**
1 hard falsification (D-03 freshness gap is Tier 1), 3 soft
falsifications (branch divergence, HTTP not HTTPS, no deployment
gate), 1 observation (no log rotation).

78 concerns tracked in the risk register: 41 resolved, 37 open/deferred.
383 tests pass.

---

## Completed Phases

### Phase 0-2c: UCDP Production Parity — COMPLETE
Full pipeline: harvest (5 sources) -> consolidate -> viewpoint ->
compile -> assemble -> export (zarr + parquet). 100% event-level
match. See `rd_roadmap02.md` for details.

### Phase 2d: Data Serving Infrastructure — COMPLETE
Caddy 2.11.2 on Hetzner (204.168.219.108), HTTP port 80, basic auth.
Consumer auth via `~/.netrc` + `aiohttp.BasicAuth` wrapper for xarray.
Cron automation on 21st at midnight UTC. Pipeline failure sentinel
(`logs/pipeline_failure.json`). Ten-check `verify_remote.py` script.
Three cron environment failures diagnosed and fixed (PATH, PS1, token).
Shapefile harvester stale-ledger bug found and fixed across all 5
harvesters (C-94, C-95).

**See:** `docs/guides/hetzner_deployment_guide.md`,
`docs/guides/hetzner_deployment_log.md`

---

## Active Directions

### Direction 1: Data Serving (infrastructure)

**Status:** Operational. Serving zarr + parquet over HTTP with basic
auth. Deployment hardening in progress (Direction 4).

### Direction 2: Three New Data Sources

Three sources under investigation. Each has its own R&D roadmap and
product plan in `reports/sources/`.

| Source | Type | Resolution | Access | Integration | Status |
|--------|------|-----------|--------|-------------|--------|
| **V-Dem** | Democracy indicators | Country-year | Free | Easy | Investigation |
| **ACLED** | Conflict + protests | Point events | Registration | Medium | Blocked (access) |
| **WID** | Inequality | Country-year | Free | Hard (conceptual) | Investigation |

**Recommended order:** V-Dem -> ACLED -> WID.

**Per-source documents:**
- V-Dem: `reports/sources/vdem_roadmap.md`, `reports/sources/vdem_plan.md`
- ACLED: `reports/sources/acled_roadmap.md`, `reports/sources/acled_plan.md`
- WID: `reports/sources/wid_roadmap.md`, `reports/sources/wid_plan.md`

### Direction 3: Raster Sources — BLOCKED on rasterio

Unchanged from v03. Population, built-up area, nightlights require
raster-to-grid aggregation. Blocked on rasterio/GDAL dependency.

### Direction 4: Deployment Hardening — NEW

Falsification audit (2026-04-01) found the system works end-to-end
but is not at deployment quality. This direction closes the gap
between "it works" and "it can be relied upon."

**Source:** `test_falsification_deployment.py` (F1-F5),
`test_falsification_netrc.py` (C-96, C-97)

#### Phase DH-1: v1.0 — Single-user research deployment

Gate: the system can be called "deployed" for the primary researcher.

| Task | Finding | Risk ref | Effort | Description |
|------|---------|----------|--------|-------------|
| DH-1.1 | F1 | D-03 | 1h | Add `export_timestamp` (ISO 8601) to zarr attrs in `export_zarr.py` |
| DH-1.2 | F2 | — | 1h | Merge development to main |
| DH-1.3 | F2 | — | 30m | Establish tagging convention, tag v1.0.0 on main |
| DH-1.4 | F4 | — | 30m | Add `/etc/logrotate.d/views-datafactory` config on server |
| DH-1.5 | — | C-29 | 2h | Add e2e integration test (realistic 3-source mini-pipeline) |

**v1.0 gate criteria:**
- No open Tier 1 items in risk register
- `main` branch is current (development merged)
- At least one semantic version tag exists (v1.0.0)
- `export_timestamp` present in zarr store attributes
- `test_falsification_deployment.py` passes (both tests)
- Log rotation configured on server
- E2e integration test exists

#### Phase DH-2: v1.1 — Multi-user / external consumers

Gate: the system can safely serve data to 5-20 research consumers.

| Task | Finding | Risk ref | Effort | Description |
|------|---------|----------|--------|-------------|
| DH-2.1 | F3 | — | 1-2d | Register domain (e.g., `data.views.uu.se`), point DNS to Hetzner |
| DH-2.2 | F3 | — | 30m | Swap Caddyfile from `:80` to domain block (auto-TLS) |
| DH-2.3 | F5 | — | 2h | Tag-based checkout in `refresh_pipeline.sh` |
| DH-2.4 | — | C-88 | 1h | Restrict SSH to PRIO/Uppsala IPs via Hetzner firewall |
| DH-2.5 | — | C-84 | 2h | Create `views-deploy` non-root service account |
| DH-2.6 | — | C-85/C-86 | 1h | Replace personal SSH key with repo-scoped deploy key |
| DH-2.7 | — | C-87 | 1h | Named SSH accounts + break-glass emergency account |
| DH-2.8 | — | C-89 | 2h | Define measurable SLO for data freshness |

**v1.1 gate criteria:**
- All v1.0 criteria met
- HTTPS with valid TLS certificate (Caddy auto-TLS via domain)
- Deployment uses tag checkout, not branch tip
- SSH restricted to institutional IPs
- Non-root service account runs pipeline
- Deploy key (not personal key) for GitHub
- Named server accounts per person
- Freshness SLO defined and measurable

#### Phase DH-3: v2.0 — Institutional / scaled deployment

Gate: meets institutional audit and compliance requirements.

| Task | Finding | Risk ref | Effort | Description |
|------|---------|----------|--------|-------------|
| DH-3.1 | — | C-97 | 1-2w | Migrate from basic_auth to OAuth2 (Caddy `forward_auth` + oauth2-proxy) |
| DH-3.2 | — | C-97 | 1w | Per-user audit trail (who accessed what, when) |
| DH-3.3 | — | C-70 | 1d | Circuit breaker for upstream APIs |
| DH-3.4 | — | C-72 | 4h | HTTP 429 `Retry-After` header parsing |
| DH-3.5 | — | C-91 | 4h | Pipeline duration tracking in provenance ledger |

**v2.0 gate criteria:**
- All v1.1 criteria met
- OAuth2 / institutional SSO for data consumers
- Per-user audit trail
- Named accounts (no shared credentials)
- Circuit breaker on upstream APIs
- Pipeline duration tracked

---

## Research Questions

### Existing (from v03, unchanged)

| RQ | Topic | Status | Depends on |
|----|-------|--------|------------|
| RQ-1 | What is the .9 data stream? | Awaiting UCDP response | Email sent 2026-03-21 |
| RQ-2 | Candidate mutability | Partially answered | — |
| RQ-3 | Can .9 be reconstructed? | Answered: NO | — |
| RQ-4 | What is production parity? | Answered | — |
| RQ-5 | Statistical profile of data | Ready to start | Assembled grid exists |
| RQ-6 | Revision history analysis | Needs full harvest | Full .9 + candidate history |

### From source expansion (unchanged)

| RQ | Topic | Status | Depends on |
|----|-------|--------|------------|
| RQ-7 | Do democracy indicators predict conflict? | Not started | V-Dem integration |
| RQ-8 | Does ACLED coverage predict UCDP violence? | Not started | ACLED integration |
| RQ-9 | Does inequality predict subnational conflict? | Not started | WID integration |
| RQ-10 | How do UCDP and ACLED compare? | Not started | ACLED integration |
| RQ-11 | Can inequality trends serve as risk indicators? | Not started | WID integration |

---

## Phase Roadmap

```
DONE:  Phase 0-2c (UCDP production parity)
       Phase 2d  (data serving infrastructure)
       |
NOW:   Direction 4, Phase DH-1 -- v1.0 deployment hardening
       Direction 2 -- source investigation (V-Dem, ACLED, WID)
       |
NEXT:  Direction 4, Phase DH-2 -- v1.1 multi-user hardening
       Phase 5 -- V-Dem integration (country-level broadcast)
       Phase 6 -- ACLED integration (second conflict source)
       |
LATER: Direction 4, Phase DH-3 -- v2.0 institutional
       Phase 7 -- WID integration (inequality indicators)
       Phase 3 -- Raster sources (blocked on rasterio)
       Phase 8 -- Cross-source analysis (RQ-7 through RQ-11)
```

---

## Risk Register

Active concerns tracked in `reports/technical_risk_register.md`
(ADR-020). 78 concerns total: 41 resolved, 37 open/deferred.

**Deployment-blocking items (resolved by DH phases):**

| Risk | Tier | Resolved by |
|------|------|-------------|
| D-03 (freshness gap) | 1 | DH-1.1 |
| C-84 (root-only) | 2 | DH-2.5 |
| C-85/C-86 (personal SSH key) | 2 | DH-2.6 |
| C-87 (no named accounts) | 2 | DH-2.7 |
| C-88 (SSH open to all IPs) | 2 | DH-2.4 |
| C-29 (no e2e test) | 4 | DH-1.5 |
| C-89 (no freshness SLO) | 4 | DH-2.8 |

**Source expansion risks (unchanged from v03):**
- ACLED access may be restricted
- Country-level broadcasting is a strong assumption
- C-44 (harvest template on 4th source), C-61 (schema evolution
  on 3rd source), C-80 (6th registry)

**New from falsification audits:**
- C-96: fsspec does not auto-read `~/.netrc` (accepted, wrapper provided)
- C-97: basic auth ceiling at 30-50 users (accepted for v1.0-v1.1, migrate at v2.0)
- C-98: no deployment gate (resolved by DH-2.3)
- C-99: no log rotation (resolved by DH-1.4)
