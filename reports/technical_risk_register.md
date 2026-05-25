# Technical Risk Register

**Date:** 2026-03-17 (updated 2026-05-25)
**Source:** Multi-expert engineering review, repo assimilation, falsification audits, expert code review (Martin, GoF, Feathers, Nygard, Kleppmann, Ousterhout, Hickey, Beck), magic-values compliance audit, stale-zarr incident 2026-04-24, pipeline verification audit 2026-04-30, ACLED integration test review 2026-05-02, ACLED test review 2026-05-03, ACLED compilation test review 2026-05-05, base documentation review 2026-05-07, ACLED harvester test review 2026-05-07, GHS-POP harvester test review 2026-05-18, GHS-POP viewpoint test review 2026-05-19, PR #53 review 2026-05-20, GHS-POP memory falsification + expert code review 2026-05-20, repo-assimilation 2026-05-20, ADR-031 compliance review 2026-05-21, harvest caching expert code review 2026-05-21, PR #59 falsification audit round 2 2026-05-21, provenance/shapefile expert code review 2026-05-21, GHS-BUILT-S review-rr triage 2026-05-22, GHS-BUILT-S coverage parity falsification 2026-05-22, GHS-BUILT-S visual audit falsification 2026-05-22, GHS-BUILT-S visual audit run 2026-05-22, C-190 resolution 2026-05-23, GHS-BUILT-S merge-readiness falsification 2026-05-23, pre-merge sprint (C-191/C-192/C-168/C-174) 2026-05-23, GHS-BUILT-S merge-readiness falsification round 2 2026-05-23, repo-assimilation v1.2.20 2026-05-24, tech-debt-cleanup investigation 2026-05-24, review-rr strategic + prioritize 2026-05-24, review-base-docs 2026-05-25
**Status:** 202 concern IDs assigned (C-28 merged into C-31, C-107 merged into C-60, C-183 merged into C-44, C-03 merged into C-176): 114 resolved, 63 open concerns (8 Tier 2, 14 Tier 3, 35 Tier 4, 6 deferred by design; 4 with fired triggers), 5 open disagreements. 94 resolved concerns as full entries + 19 early-archive reference rows + 24 resolved disagreements in archive. 29 disagreement IDs total: 24 resolved, 5 open.
**Archive:** Resolved concerns and disagreements are in `archive/technical_risk_register_resolved.md`.

**Ranking criteria:** Impact if wrong x likelihood x detectability. Items marked **[DEFER]** are accepted risks or wait for a specific trigger condition. See ADR-020 for governance rationale.

---

## Open Items Summary

| ID | Tier | Title | Trigger | Package |
|----|------|-------|---------|---------|
| C-88 | 2 | SSH not restricted to PRIO/Uppsala IPs | Before granting additional SSH users | Server hardening |
| C-121 | 4 | Phase 6.4 documented but unexecuted (lessons from C-87) | Before executing Phase 6.4 | Server hardening |
| C-21 | 4 | No characterization tests for migration | No migration planned | — |
| C-36 | 4 | UCDP API contract has no schema versioning | UCDP announces API v2 | UCDP schema |
| C-37 | 4 | `date_prec=5` semantics hardcoded | UCDP publishes codebook | UCDP schema |
| C-45 | 4 | No Parquet schema evolution strategy | UCDP removes/renames a field | UCDP schema |
| ~~C-31~~ | ~~4~~ | ~~Candidate source depends on annual source (incl. C-28)~~ | Resolved 2026-04-27 | Code cleanup |
| C-44 | 4 | Harvest pipeline template is implicit — trigger fired, accepted at v1.0 | Before V-Dem (9th source) | V-Dem readiness |
| C-46 | 4 | No ledger write idempotency | External systems consume ledger | — |
| C-32 | — | Source registry returns `Any` | Accepted by design | — |
| C-29 | 4 | No end-to-end integration test — trigger fired, accepted at v1.0 | 2nd deployment target set up | Test infra |
| C-70 | 4 | No circuit breaker for UCDP API | Multi-operator deployment | UCDP resilience |
| C-72 | 4 | HTTP 429 not distinguished from 500 | UCDP returns 429s | UCDP resilience |
| C-74 | 4 | CompilationConfig leaks strategy vocabulary | New developer needs IDE discoverability | — |
| C-75 | 4 | FeatureFrame shallow abstraction | Consumer constructs wrong shape | — |
| C-78 | 4 | `_place_events` hard to test in isolation | Compilation tests exceed 5s | Test infra |
| C-79 | 4 | Compilation/consolidation require real Parquet I/O | Test suite exceeds 30s | Test infra |
| ~~C-03~~ | ~~4~~ | ~~Protocol proliferation in synthetic module~~ | Subsumed into C-176 | — |
| C-93 | 4 | `_count_outcomes` mixes raw counts with derived computation | When harvest reporting is refactored | Code cleanup |
| C-96 | 4 | fsspec does not auto-read `~/.netrc` | If fsspec adds netrc support | — |
| C-97 | 4 | Basic auth + Caddy scalability ceiling at ~30-50 users | Before consumer count exceeds 30 | — |
| C-109 | 4 | Advisory file locks (fcntl) don't work across NFS | Pipeline migrates to network FS | — |
| C-115 | 4 | Summary detection threshold (>= vs >) is architectural | UCDP changes definition | ADR-023 |
| C-116 | 4 | No retry on remote zarr network failures | Consumer reports transient failures | Query resilience |
| C-117 | 4 | Remote zarr downloads all spatial cells before region filter | Consumer queries single country over slow connection | Query performance |
| ~~C-128~~ | ~~2~~ | ~~Scripts infer grid shape without config validation (ADR-003 forbidden)~~ | Resolved 2026-04-27 | ADR-003 compliance |
| ~~C-127~~ | ~~2~~ | ~~Zarr backend returns features in alphabetical order, npy preserves feature_names.json order~~ | Resolved 2026-04-27 | Query correctness |
| C-129 | 3 | Partition boundaries (month IDs) have no single source of truth | VIEWS shifts partition boundaries | ADR-003 compliance |
| C-130 | 2 | Zero-filled future months indistinguishable from observed zeros | Model trains on months beyond last UCDP update | Data boundary |
| C-131 | 2 | No external monitoring for cron job failure on Hetzner | Server reboots without cron re-enable or user deletion | Operational monitoring |
| C-132 | 2 | Health check validates export timestamp, not data recency | UCDP API returns empty/stale data during pipeline run | Operational monitoring |
| C-133 | 3 | Zero-padding warning only fires for integer `end` parameter | Consumer calls load_dataset with string date or end=None | Data boundary |
| ~~C-134~~ | ~~3~~ | ~~`get_last_valid_month_id()` silently returns None on all errors~~ | Resolved 2026-04-27 | Data boundary |
| C-135 | 4 | No runtime type validation for zarr `.zattrs` values | Manual edit of `.zattrs` on server | Data boundary |
| C-136 | 4 | `read_last_entries()` crashes on non-UTF8 ledger files | Disk corruption or binary append to JSONL ledger | Operational monitoring |
| C-137 | 2 | No round-trip integrity check after zarr export | Pipeline export produces truncated or partial zarr store | Data integrity |
| C-138 | 2 | No post-deploy data correctness verification | Pipeline completes but served data doesn't match assembled grid | Data integrity |
| C-139 | 2 | Consumer parity tests check per-cell rates but not aggregate totals | Systematic undercounting passes per-cell threshold | Data integrity |
| C-149 | 2 | 603 unmapped GAUL cells silently excluded from CM aggregation | Consumer trains CM model without awareness of 4% fatality gap | Data integrity |
| ~~C-140~~ | ~~2~~ | ~~v1.2.6/v1.2.7 incident fixes have zero test coverage~~ | Resolved 2026-04-26 | Data integrity |
| ~~C-141~~ | ~~3~~ | ~~UCDP config class validation partially untested~~ | Resolved 2026-04-26 | Test coverage |
| ~~C-142~~ | ~~3~~ | ~~datafactory_query consumer entry point has zero Red/Beige tests~~ | Resolved 2026-04-26 | Test coverage |
| ~~C-143~~ | ~~4~~ | ~~request_with_retry has no Red tests~~ | Resolved 2026-04-26 | Test coverage |
| ~~C-125~~ | ~~3~~ | ~~No cm aggregation — 48/70 models cannot migrate~~ | Resolved 2026-04-21 | Migration scope |
| C-126 | 3 | No transform layer — 14 viewser transforms not replaceable | Model migration requires derived features | Migration scope |
| C-177 | 4 | `_aggregate_to_prio_grid` holds source + copy simultaneously (ADR-031 P3) | Function is re-activated for a new data source | ADR-031 compliance |
| ~~C-178~~ | ~~3~~ | ~~`compute_content_digest(path.read_bytes())` loads entire output into memory~~ | Resolved 2026-05-21 | ADR-031 compliance |
| C-179 | 4 | Consolidation dedup uses `.to_pylist()` + Python set (ADR-031 P1) | Consolidated store exceeds ~5M rows on 8 GB machine | ADR-031 compliance |
| C-180 | 4 | No falsification tests for non-GHS-POP compilation/viewpoint paths | Memory regression introduced in UCDP or ACLED path | Test coverage |
| C-181 | 4 | UCDP candidate/dot9 discovery probes API even when all versions cached | UCDP rate-limits or blocks IP after repeated full-range probes | Harvest efficiency |
| ~~C-182~~ | ~~2~~ | ~~`last_digest_for_version` returns digest from failed ledger entries~~ | Resolved 2026-05-21 | Harvest correctness |
| C-184 | 3 | ACLED `_year_is_cached` checks file existence, not file integrity | Truncated/corrupted Parquet accepted as valid cache hit | Harvest correctness |
| C-185 | 4 | GHS-POP caching has no digest comparison (no change detection) | JRC silently updates a GeoTIFF epoch without changing the URL | Harvest correctness |
| C-186 | 3 | Shapefile harvester lacks outcome vocabulary; ADR-032 overstates compliance | New harvester trusts ADR-032 claim that all harvesters record failed entries | Harvest correctness |
| ~~C-187~~ | ~~4~~ | ~~Digest-field assumption in reverse scan shadows valid entries~~ | Resolved 2026-05-21 | Provenance correctness |
| ~~C-188~~ | ~~3~~ | ~~GAUL admin failure path writes no ledger entry~~ | Resolved 2026-05-21 | Harvest correctness |
| C-189 | 3 | GHS-BUILT-S test coverage parity gap — 19% of combined other sources | Production incident on GHS-BUILT-S path that existing GHS-POP/ACLED tests would have caught | Test coverage |
| ~~C-190~~ | ~~4~~ | ~~KNOWN_GLOBAL_BUILT_AREA reference values ~6-7x actual JRC totals~~ | Resolved 2026-05-23 | Visual audit |
| ~~C-191~~ | ~~2~~ | ~~`refresh_pipeline.sh` has no GHS-BUILT-S steps — feature dead on arrival in production~~ | Resolved 2026-05-23 | Operations |
| ~~C-192~~ | ~~3~~ | ~~Operational integration consistently trails implementation — 3rd recurrence~~ | Resolved 2026-05-23 | Workflow process |
| D-23 | — | ADR-031 P1 strict columnar purity vs pragmatic materialization | Open | ADR-031 compliance |
| D-24 | — | Hardware upgrade vs software optimization for 8 GB ceiling | Open | ADR-031 compliance |
| ~~D-25~~ | ~~—~~ | ~~Dead function retention — `_aggregate_to_prio_grid` after v1.2.18~~ | Resolved 2026-05-24 | ADR-031 compliance |
| D-26 | — | Discovery probing cost vs cache staleness (UCDP candidate/dot9) | Open | Harvest caching |
| D-27 | — | Two-tier cache (UCDP) vs single-tier cache (ACLED/GHS-POP) | Open | Harvest caching |
| ~~D-28~~ | ~~—~~ | ~~One function vs two for digest lookup (`last_digest` + `last_digest_for_version`)~~ | Resolved 2026-05-24 | Provenance API |
| D-29 | — | Shapefile harvester retrofit depth — full outcome compliance vs organic | Open | Harvest correctness |
| C-144 | 3 | Compilation `to_pydict()` materializes millions of Python objects | Consolidation store exceeds ~5M events | Compilation memory |
| C-145 | 3 | Viewpoint builder loads full consolidated store into memory | Consolidated store exceeds ~5M rows on constrained hardware | Viewpoint memory |
| C-146 | 3 | Assembly logic lives in script, not importable package | Assembly orchestration refactored or new assembly path added | Testability |
| C-147 | 4 | No pipeline orchestrator in repository | Operator runs scripts out of order or skips a step | Operations |
| C-148 | 4 | Hardcoded Hetzner server IP in `defaults.py` | Server migrates to new IP or hostname | Configuration |
| ~~C-150~~ | ~~2~~ | ~~Zero Red team tests for ACLED pipeline~~ | Resolved 2026-05-02 | ACLED test coverage |
| ~~C-151~~ | ~~3~~ | ~~No CICs for ACLED config classes~~ | Resolved 2026-05-02 | ACLED test coverage |
| ~~C-152~~ | ~~3~~ | ~~ACLED profiles and `list_acled_profiles()` untested~~ | Resolved 2026-05-02 | ACLED test coverage |
| C-153 | 3 | ACLED API has no TotalCount — silent truncation undetectable | ACLED enforces server-side result caps within a page | ACLED data integrity |
| C-154 | 4 | ACLED_FEATURES config duplicated between script and tests | Feature filter values changed in script but not tests | ACLED test quality |
| C-155 | 4 | No shared visual audit framework — per-source scripts are idiosyncratic | 5th data source (V-Dem or WDI) requires a 5th bespoke verify script | Visual audit |
| C-195 | 4 | 37 falsification test files accumulated without curation (3,129 lines) | 5th source adds another 5-8 falsification files, pushing total past 40 | Test hygiene |
| ~~C-196~~ | ~~4~~ | ~~7 of 8 ARCHITECTURE.md files have stale module lists~~ | Resolved 2026-05-25 | Documentation drift |
| ~~C-197~~ | ~~4~~ | ~~docs/CICs/README.md lists 21 active contracts but 28 exist~~ | Resolved 2026-05-25 | Documentation drift |
| ~~C-198~~ | ~~4~~ | ~~docs/sources/README.md references 4 catalog cards that don't exist~~ | Resolved 2026-05-25 | Documentation drift |
| ~~C-199~~ | ~~3~~ | ~~ADR-026 ACLED credential env vars contradict code~~ | Resolved 2026-05-25 | ADR drift |
| ~~C-200~~ | ~~3~~ | ~~Grid dimension order wrong in ADR-005 and CLAUDE.md~~ | Resolved 2026-05-25 | ADR drift |
| ~~C-201~~ | ~~4~~ | ~~4 CICs with contract drift post-v1.2.21~~ | Resolved 2026-05-25 | CIC drift |
| ~~C-202~~ | ~~4~~ | ~~Operational docs stale — logging standard, deployment guide, hardened protocol, ADR counts~~ | Resolved 2026-05-25 | Documentation drift |
| ~~C-168~~ | ~~3~~ | ~~TemporalConfig defaults to end_year=2024 — footgun for new sources~~ | Resolved 2026-05-23 | ADR-003 compliance |
| ~~C-169~~ | ~~4~~ | ~~2 CI tests fail due to missing infrastructure (netrc, sibling repo)~~ | Resolved 2026-05-25 | Test infra |
| ~~C-170~~ | ~~1~~ | ~~GHS-POP viewpoint list accumulation OOM (~6.5 GB Python objects)~~ | Resolved 2026-05-20 | GHS-POP memory |
| ~~C-171~~ | ~~1~~ | ~~Pregridded compilation `.to_pylist()` OOM (~6 GB Python objects)~~ | Resolved 2026-05-20 | GHS-POP memory |
| ~~C-172~~ | ~~3~~ | ~~Latent OOM in `_aggregate_to_prio_grid` dead branch~~ | Resolved 2026-05-20 | GHS-POP memory |
| C-173 | 3 | Hetzner CPX32 has no swap — OOM kills with zero safety net | Any transient memory spike above physical RAM on server | Server hardening |
| ~~C-167~~ | ~~4~~ | ~~reports/audit_ghspop/ not in .gitignore~~ | Resolved 2026-05-20 | GHS-POP hygiene |
| C-164 | 3 | Cross-layer WET debt: 3 sources replicate patterns across all 4 layers | 4th source (V-Dem or WDI) requires copying 6+ structural patterns | WET-before-DRY |
| C-156 | 3 | ACLED temporal range mismatch — zero-fill before 2020 in assembled grid | Model uses ACLED features for pre-2020 months without awareness of zero-fill | ACLED assembly |
| ~~C-174~~ | ~~3~~ | ~~`latlon_to_pgid` silently clamps out-of-bounds coordinates~~ | Resolved 2026-05-23 | Compilation correctness |
| C-175 | 3 | Aggregation missing-field coalesced to zero, not NaN | Source removes or renames a field used in `FeatureSpec` | Compilation correctness |
| ~~C-176~~ | ~~4~~ | ~~`datafactory_synthetic` is a dead module with zero exports~~ | Resolved 2026-05-25 | Code cleanup |
| C-159 | 4 | ACLED snapshot archiving and revision comparison paths untested | Archiving logic implicated in data integrity incident | ACLED test coverage |
| C-160 | 4 | ACLED `fetch_paginated` string-data corruption has no guard | ACLED API returns non-list `data` field | ACLED data integrity |
| ~~C-161~~ | ~~4~~ | ~~GHS-POP harvester failure-path provenance partially untested~~ | Resolved 2026-05-18 | GHS-POP test coverage |
| ~~C-165~~ | ~~1~~ | ~~GHS-POP viewpoint OOM: 22 GB peak on 8 GB server~~ | Resolved 2026-05-20 | GHS-POP memory |
| ~~C-162~~ | ~~1~~ | ~~GHS-POP PGID mapping has no direct correctness test~~ | Resolved 2026-05-19 | GHS-POP data integrity |
| ~~C-166~~ | ~~2~~ | ~~GHS-POP absent from PIPELINE_SOURCES — verify_remote.py blind~~ | Resolved 2026-05-20 | GHS-POP observability |
| ~~C-163~~ | ~~2~~ | ~~`_aggregate_to_prio_grid` silently truncates non-divisible raster dimensions~~ | Resolved 2026-05-19 | GHS-POP data integrity |
| ~~C-157~~ | ~~3~~ | ~~Systematic ACLED documentation drift across ADRs, CICs, and guides~~ | Resolved 2026-05-07 | Documentation |
| ~~C-158~~ | ~~4~~ | ~~No CICs for SourceEntry or AssemblyConfig~~ | Resolved 2026-05-07 | Documentation |
| ~~C-122~~ | ~~3~~ | ~~Consumer model has no runtime data fetch from Hetzner~~ | Resolved 2026-04-19 | Consumer integration |
| ~~C-123~~ | ~~4~~ | ~~`africa_me_legacy` region file not distributed~~ | Resolved 2026-04-19 | Consumer integration |
| ~~C-124~~ | ~~4~~ | ~~No consumer onboarding for remote zarr credentials~~ | Resolved 2026-04-19 | Consumer integration |
| ~~C-193~~ | ~~4~~ | ~~Deployment guide GHS-BUILT-S download size overstated (~5 GB vs ~2.1 GB)~~ | Resolved 2026-05-23 | Documentation |
| ~~C-194~~ | ~~4~~ | ~~Raster harvesters lack `logger.error` before bare `raise` — ADR-008~~ | Resolved 2026-05-23 | ADR-008 compliance |
| C-10 | — | Ontology vocabulary overhead | Accepted | — |
| C-38 | — | Version string year offset assumes 21st century | Never (2099) | — |
| C-41 | — | Digest truncation collision risk | Records exceed 100M | — |
| C-06 | — | Provenance composability | Deferred by design | — |
| C-07 | — | Frozen dataclass pattern repeated | Deferred by design | — |

## Work Packages

Items that should be resolved together:

| Package | Items | Trigger |
|---------|-------|---------|
| **Server hardening** | C-88, C-121, C-173 (C-84, C-85, C-86, C-87 resolved) | Before production deployment |
| **V-Dem readiness** | C-44 (C-91 resolved) | Before V-Dem integration |
| **UCDP API resilience** | C-70, C-72 | Multi-operator deployment |
| **Compilation correctness** | ~~C-174~~, C-175 | Source with unvalidated coordinates or renamed fields (C-174 resolved) |
| **UCDP schema defense** | C-36, C-37, C-45, C-175 | UCDP API change |
| **Test infrastructure** | C-29, C-78, C-79, C-146, C-169 | Test suite growth (C-60 resolved) |
| **Code cleanup** | ~~C-31~~, C-93, C-176 | Next refactor opportunity (C-80, C-112, C-31 resolved) |
| ~~**Consumer integration**~~ | ~~C-122, C-123, C-124~~ | ~~Resolved~~ |
| ~~**Query correctness**~~ | ~~C-127~~ | Resolved 2026-04-27: warning on fallback, export already writes feature_order |
| **ADR-003 compliance** | ~~C-128~~, C-129, ~~C-168~~ | Before next assembly/compilation change (C-128, C-168 resolved) |
| **Operational monitoring** | C-131, C-132, C-136, C-147, ~~C-191~~ | Before relying on Hetzner pipeline without manual checks (C-191 resolved) |
| **Scaling headroom** | C-144, C-145 | Before consolidated store exceeds ~5M rows |
| **Data integrity** | C-137, C-138, C-139, C-149 | Before relying on served data for model training |
| **Data boundary** | C-130, C-133, ~~C-134~~, C-135 | Before consumer models train on data from the factory (C-134 resolved) |
| ~~**GHS-POP deployment**~~ | ~~C-165, C-166, C-167~~ | Resolved 2026-05-20 |
| ~~**GHS-POP memory**~~ | ~~C-170, C-171, C-172~~ | Resolved 2026-05-20 |
| **Harvest correctness** | ~~C-182~~, C-184, C-185, C-186, ~~C-188~~ | Before relying on harvest caching for correctness |
| **WET-before-DRY refactor** | C-44, C-07, C-155, C-164, C-195 | Before 5th source (V-Dem or WDI) |
| ~~**Test coverage**~~ | ~~C-140, C-141, C-142, C-143~~ | Resolved 2026-04-26: 32 tests added |
| ~~**ACLED test coverage**~~ | ~~C-150, C-151, C-152~~ | Resolved 2026-05-02: 13 Red tests + 5 profile tests + 3 CICs added |
| **Migration scope** | ~~C-125~~, C-126 | Before claiming full viewser replacement for the fleet |
| ~~**Workflow process**~~ | ~~C-192~~ | Resolved 2026-05-23 |
| ~~**Documentation drift**~~ | ~~C-157, C-158~~ | Resolved 2026-05-07: 19 docs updated, 2 CICs created |

---

## Tier 1 — Fix Immediately

---

## Tier 2 — Fix Before Sharing Server Access

### C-88: SSH not restricted to PRIO/Uppsala IPs — [DEFER]
SSH is open to all source IPs. IT head advised whitelisting PRIO and Uppsala VPN IPs via fail2ban or Hetzner firewall, requiring VPN for SSH access. **Trigger: before granting additional SSH users, or when PRIO IT provides VPN CIDR ranges for firewall rules (trigger rewritten during review-rr 2026-05-24).** Procedure documented in `hetzner_deployment_guide.md` Phase 6.4. Requires PRIO/Uppsala VPN CIDR ranges from IT.
**Source:** PRIO IT security guidance, server setup 2026-03-28

### C-130: Zero-filled future months indistinguishable from observed zeros — [RESOLVING]
The assembled grid is pre-allocated through `--end-year 2026` (456 months) but UCDP data only covers through the most recent release (~Feb/Mar 2026 as of April 2026). Months beyond the last UCDP update contain zeros in all `ged_*` features. `load_dataset()` returns these zero-filled months without any signal that they are padding, not observations. A model training on months 121–560 would learn that conflict drops to zero after the data boundary — silent data corruption.

**Fix applied:** Added `last_valid_month_id` metadata to zarr `.zattrs` (via `export_zarr.py`) and npy `provenance.json` (via `assemble_grid.py`). `load_dataset()` now emits `UserWarning` when `end` exceeds the boundary. `get_last_valid_month_id()` exposed in `datafactory_query.defaults` for consumer partition logic. **Remaining:** Remote zarr store on Hetzner still lacks the attribute (confirmed 2026-04-22, falsification P5). All remote consumers get `None` and no warning until redeploy. Cross-ref: C-133 (warning bypass for non-integer end).

**Trigger:** Model trains on months beyond last UCDP update without awareness.
**Location:** `scripts/export_zarr.py`, `scripts/assemble_grid.py`, `src/datafactory_query/dataset.py`, `src/datafactory_query/defaults.py`.
**Source:** Falsification audit F9 (2026-04-22), updated with P5 finding (2026-04-22).

### C-131: No external monitoring for cron job failure on Hetzner — [RESOLVING]
The monthly pipeline runs via a single cron job (`0 0 21 * *`) under the `views-deploy` user. If the cron daemon crashes, the server reboots without re-enabling cron, or the `views-deploy` user is deleted during maintenance, the pipeline silently stops running. No external monitoring (cronitor, uptime check, systemd watchdog) exists to detect this. ADR-018 explicitly defers monitoring to operators (line 76: "Operators must monitor and intervene during outages") but no operator-side monitoring has been configured. The `ALERT_EMAIL` variable in `refresh_pipeline.sh:68` is a documented TODO (deployment log line 332) and is not set on the server.

**Fix applied (2026-04-22):** Added optional heartbeat ping to `refresh_pipeline.sh` — on successful pipeline completion, pings `$HEARTBEAT_URL` (env var) if set. Operator must configure a healthchecks.io/cronitor service and set the URL on the server. Architectural review confirmed this is a deployment concern (not a new module) per ADR-018.

**Trigger:** Hetzner server reboots and cron daemon fails to restart, or `views-deploy` user is removed during server maintenance.
**Location:** Server crontab (`views-deploy` user), `scripts/refresh_pipeline.sh:61-72` (failure trap), `docs/ADRs/018_operational_resilience.md:76,90`.
**Source:** Falsification audit P1/P2 (2026-04-22).

### C-132: Health check validates export timestamp, not data recency — [RESOLVING]
`check_export_freshness()` in `health.py:124-182` reads `export_timestamp` from zarr `.zattrs` and compares against the 168-hour SLO. Previously did not read `last_valid_month_id`. A pipeline run where the UCDP API returns empty pages or cached data (API outage, rate limit, network issue) would still complete all 7 steps, update `export_timestamp`, and pass the health check — while the actual data boundary has not advanced.

**Fix applied (2026-04-22):** `check_export_freshness()` now reads `last_valid_month_id` from `.zattrs`, computes expected minimum from current date (allowing 2-month UCDP release lag), and returns `data_boundary_current` boolean. `check_health.py` displays data boundary status and flags `STALE` when boundary hasn't advanced. **Remaining:** Takes effect on Hetzner after redeploy (same as C-130).

**Trigger:** UCDP API returns empty pages or cached data during the monthly pipeline run.
**Location:** `src/datafactory_provenance/health.py:124-195` (`check_export_freshness`), `scripts/check_health.py:111-128`.
**Source:** Falsification audit P3 (2026-04-22). Cross-ref: C-130 (zero-padding metadata).

### C-149: 603 unmapped GAUL cells silently excluded from CM aggregation — [RESOLVING]
603 PRIO-GRID cells in `africa_me_legacy` (and ~1,800 in `land`) have centroids that fall outside any FAO GAUL polygon — coastal cells, small islands, boundary edge cases. These cells are assigned `gaul0_code = -1` during assembly. `grid_to_country_month()` filters on `country_ids > 0`, silently dropping these cells from CM output. The dropped cells carry significant fatalities: 45,593 sb_best, 6,012 ns_best, 7,986 os_best across 435 months, with single-month peaks up to 2,688. This creates a ~4% systematic gap between PGM and CM fatality totals. A model training on CM data (e.g., shining_codex) sees fewer total fatalities than a model training on PGM data (e.g., heavy_freighter) for the same region and time range, with no warning.

**Fix applied (2026-04-30):** Added verification tests (`test_model_parity.py::TestCMParity`, `test_pipeline_consistency.py::TestPGMCMAggregation`) that explicitly account for the gap by filtering PGM to `gaul0_code > 0` in internal consistency checks and using bounded tolerances for gold set comparison. **Remaining:** No runtime warning when CM aggregation drops cells with events. Consumer has no way to discover which cells are excluded or quantify the gap. Resolution options: (a) emit warning/metadata listing excluded pgids and their event totals, (b) improve GAUL spatial join to capture more coastal cells via buffered centroids or polygon-edge matching.

**Trigger:** Consumer trains a CM model and observes unexplained discrepancy vs PGM totals, or adds a new region with more coastal cells where the gap is larger.
**Location:** `src/datafactory_adapters/grid_to_country_month.py:72-76` (land_mask filter), `scripts/assemble_grid.py:177-179` (gaul0_code = -1 fill), `src/datafactory_harvester/sources/gaul_admin.py:358-359` (unmatched centroids skipped).
**Source:** Pipeline verification audit 2026-04-30. Cross-ref: C-125 (CM aggregation implementation), C-139 (aggregate total checks).

### C-137: No round-trip integrity check after zarr export — [RESOLVING]
`export_zarr.py` writes the assembled grid to a zarr store but never reads it back to verify the data survived the write. A truncated write, chunking bug, or partial store would produce a zarr store with wrong values and no error signal. This is the exact failure mode that caused the 46% fatality gap on the Hetzner server: the served zarr store had missing pre-2014 data, but the export step reported success.

**Fix applied (2026-04-24):** Added round-trip sum verification to `export_zarr.py` — after writing and consolidating the zarr store, reads back each feature and asserts `zarr_sum == grid_sum`. Exits with code 1 on mismatch, halting the pipeline.

**Trigger:** Pipeline export produces a truncated or partial zarr store (disk full, timeout, corrupted chunk).
**Location:** `scripts/export_zarr.py` (after `ds.to_zarr()` and `zarr.consolidate_metadata()`).
**Source:** Stale-zarr incident 2026-04-24. Cross-ref: C-130 (zero-padding), C-132 (health check gap).

### C-138: No post-deploy data correctness verification — [DEFER]
The health check (`check_health.py`) validates metadata freshness (export timestamp, data boundary month) but never checks whether the data values in the served zarr store are correct. A zarr store that passes all metadata checks but contains wrong values (stale data, partial export, corrupted chunks) is invisible to the current monitoring stack. The Hetzner zarr store served data with 46% missing fatalities for weeks while all health checks passed.

**Trigger:** Pipeline completes successfully but the HTTP-served zarr store doesn't match the local assembled grid.
**Location:** `scripts/check_health.py`, `scripts/refresh_pipeline.sh` (step 7).
**Resolution:** Add a `verify_remote_data.py` script that fetches a small slice from the HTTP endpoint and compares totals against the local grid. Run as pipeline step 8.
**Source:** Stale-zarr incident 2026-04-24. Cross-ref: C-137 (export integrity), C-132 (health check gap).

### C-139: Consumer parity tests check per-cell rates but not aggregate totals — [RESOLVING]
`test_consumer_parity.py` asserts that per-cell mismatches stay below 0.1% but does not check whether the global sum of fatalities matches between the data factory and the reference dataset. Systematic undercounting — where many cells have 0 instead of small nonzero values — passes the per-cell threshold (each zero-vs-nonzero cell is one mismatch out of 4.8M rows) while producing a 46% total gap. This is exactly what happened: per-cell parity was 99.98% while the aggregate total was off by 347,797 fatalities.

**Fix applied (2026-04-24):** Added global sum assertion to `assert_consumer_parity()` in `test_consumer_parity.py`. For each feature column, asserts `abs(factory_total - reference_total) / reference_total <= 0.1%`.

**Trigger:** Systematic event loss affecting many cells (e.g., missing year range, filtered violence type, wrong aggregation strategy).
**Location:** `tests/test_consumer_parity.py:127-145` (`assert_consumer_parity` feature checks).
**Source:** Stale-zarr incident 2026-04-24. Cross-ref: C-137 (export integrity).

---

## Tier 3 — Improve Quality

### C-133: Zero-padding warning only fires for integer `end` parameter — [RESOLVING]
Previously the `UserWarning` in `load_dataset()` only fired when `end` was an integer. String dates (`"2027-06"`) and `end=None` silently returned zero-filled months.

**Fix applied (2026-04-22):** Warning moved to after time slicing. Now computes effective end month_id from `time_steps[-1]` (the actual loaded data), not from the `end` parameter. Fires for all three calling patterns: integer end, string end, and `end=None`. Confirmed by falsification tests P4 and P6.

**Trigger:** New consumer or notebook calls `load_dataset()` with string end date or without explicit `end` parameter.
**Location:** `src/datafactory_query/dataset.py` (warning gate, post-time-slice).
**Source:** Falsification audit P4/P6 (2026-04-22). Cross-ref: C-130 (zero-padding metadata).

### C-129: Partition boundaries (month IDs) have no single source of truth
The calibration/validation/forecasting partition boundaries (121/444, 445/492, 493/540) appear as bare literals in 4+ independent locations: `scripts/generate_consumer_data.py:56` (`PARTITIONS` dict), `examples/ex_partitions.py` (6+ occurrences in assertions), `tests/test_consumer_data.py:162,169`, and downstream in `bright_starship/configs/config_partitions.py`. No shared authoritative definition exists. Adding a new partition type or shifting a boundary (e.g., extending calibration) requires coordinated find-and-replace across repos with no compiler or test to catch a missed update. Per ADR-003: "a single source of truth must be designated."

**Trigger:** VIEWS operational calendar shifts partition boundaries (e.g., extending calibration end from month 444 to 456).
**Location:** `scripts/generate_consumer_data.py:56`, `examples/ex_partitions.py:21-101`, `tests/test_consumer_data.py:162,169`, `tests/test_consumer_parity.py:57`, downstream `bright_starship/configs/config_partitions.py`.
**Resolution:** Define a `PARTITIONS` frozen dict or dataclass in a shared location within `src/` and have all consumers import from it.
**Source:** Magic-values compliance audit 2026-04-21. Cross-ref: ADR-003 (single source of truth).

### C-126: No transform layer — models using viewser transforms cannot migrate — [DEFER]
14 distinct viewser transforms are in active use across the fleet: `replace_na`, `fill`, `tlag` (832 uses), `countrylag` (486), `gte` (316), `decay` (288), `time_since` (285), `ln` (233), `moving_sum`, `spatial.lag`, `sptime_dist`, `treelag`, `delta`, `moving_average`. The factory provides raw values + `fillna(0)` only. Models using any transform beyond fillna cannot migrate without reimplementing those transforms outside viewser. The transform layer will likely be a separate repo or integrated into model classes (hydranet, r2darts2, stepshifter) — too early to decide architecture. **Trigger: model migration plan requires features derived from viewser transforms.**
**Source:** Falsification audit 2026-04-20 (F7). Cross-ref: S2 in `test_falsification_viewser_replacement.py`.

### C-144: Compilation `to_pydict()` materializes millions of Python objects — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-144 |
| Tier | 3 |
| Source | repo-assimilation (2026-04-30) |
| Trigger | When the consolidated store exceeds ~5M events (currently ~2.3M), compilation memory usage on the CPX32 server (32GB) may exceed available RAM |
| Location | `src/datafactory_compilation/grid_compilation.py:119-155` (`_place_events_columnar`, Phase 2: `table.to_pydict()`) |

`_place_events_columnar` uses a two-phase approach: Phase 1 extracts only lat/lon/date as Python lists for bin assignment (efficient). Phase 2 calls `table.to_pydict()` on the full table (~40 columns), creating a dict of 40 lists with ~2.3M elements each, then constructs individual event dicts for every placed event. This is the dominant memory allocation. Production reports ~30s completion, so it works today, but scales linearly with event count. The performance test (`test_performance.py`) uses only 50 events, so this path is untested at production scale. Currently mitigated by sufficient server RAM (32GB).

See also C-78 (`_place_events_columnar` testability). The pregridded variant (`pregridded_compilation.py`) had the same pattern with `.to_pylist()` and was fixed in C-171 by replacing with `.to_numpy()`.

### C-145: Viewpoint builder loads full consolidated store into memory — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-145 |
| Tier | 3 |
| Source | repo-assimilation (2026-04-30) |
| Trigger | When the consolidated store exceeds ~5M rows on a memory-constrained machine, or when building viewpoints on developer laptops with <16GB RAM |
| Location | `src/datafactory_viewpoint/builders/ucdp_v1.py:129` (`pq.read_table(config.consolidated_path)`) |

`build_ucdp_v1` calls `pq.read_table()` which materializes the entire consolidated Parquet store as a PyArrow Table. The table is then sorted by `id` (creating a second copy), and iterated as groups of Python dicts. The docstring notes peak memory was reduced from ~4GB to ~1GB via streaming output columns, but the initial `pq.read_table` plus the sorted copy still dominate. At ~2.3M events with ~45 columns this is manageable on the 32GB server. A future migration to row-group streaming or predicate pushdown would decouple viewpoint memory from store size. **Update 2026-05-21 (ADR-031 review):** Output accumulation at lines 257-303 builds a dict-of-lists (~1.3 GB at current data volume) — an ADR-031 P1 spirit violation. Currently harmless because UCDP data volume is ~60x smaller than GHS-POP, but will become acute if consolidated store grows significantly.

See also C-79 (Parquet I/O in tests), C-179 (consolidation dedup to_pylist).

### C-146: Assembly logic lives in script, not importable package — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-146 |
| Tier | 3 |
| Source | repo-assimilation (2026-04-30) |
| Trigger | When assembly orchestration needs refactoring, or a second assembly path is needed (e.g., different feature sets for different consumers) |
| Location | `scripts/assemble_grid.py` (~350 LOC procedural, not in any `src/datafactory_*` package) |

Every other layer exposes its core logic as an importable function: `consolidate_ucdp()`, `build_ucdp_v1()`, `compile_grid()`, `load_dataset()`. Assembly is the exception — its spatial join, static feature broadcast, and admin boundary merge logic lives entirely in `assemble_grid.py`'s `main()`. `test_assemble.py` tests sub-components (spatial join helper, GID lookup) but cannot import and test the orchestration function directly. Extracting an `assemble_grid()` function into `datafactory_compilation` or a new `datafactory_assembly` package would make the logic importable and directly testable.

**Note (2026-05-24, repo-assimilation v1.2.20):** At 4 sources / 831 lines, the script grows linearly per source (~100-150 lines per source for loading, slicing, and stacking). At source #8-10, `assemble_grid.py` will exceed 1,200 lines of procedural code with no importable interface. The linear growth compounds the testability concern: each new source adds code paths that cannot be unit-tested in isolation.

**Note (2026-05-24, tech-debt-cleanup investigation):** The linear growth mechanism is now identified: lines 240-441 contain 3 source load-validate-align blocks (ACLED 59 lines, GHS-POP 66 lines, GHS-BUILT-S 77 lines = 202 lines total) that are **structurally identical** with only variable-name substitution. Each block: load grid.npy + feature_names.json + time_steps.npy → assert existence → assert_grid_shape → find temporal offset → validate bounds → print diagnostics. A parameterized `_load_source_grid(name, grid_dir, time_steps)` function (~40 lines) would replace all 3 blocks and handle the 5th source without new code. Extraction is safe (no memory or behavioral change — same np.load with mmap_mode="r"), but the function must remain in the script until C-146's testability concern is also addressed (extraction to importable package).

See also C-29 (no end-to-end integration test), C-164 (cross-layer WET debt).

### ~~C-168~~: TemporalConfig defaults to end_year=2024 — footgun for new pipeline sources

| Field | Value |
|-------|-------|
| ID | C-168 |
| Tier | 3 |
| Source | PR #53 review, GHS-POP post-mortem (2026-05-20) |
| Trigger | Resolved 2026-05-23 |
| Location | `src/datafactory_priogrid/temporal_config.py:29` |

**Resolved 2026-05-23.** Fix: Updated `TemporalConfig` default from `end_year=2024` to `end_year=2026`. This matches what all 5 pipeline scripts already use explicitly. `DEFAULT_TEMPORAL_CONFIG` now produces 456 months (1989-01 to 2026-12). Making `end_year` required (no default) was considered but rejected — it would break `DEFAULT_TEMPORAL_CONFIG = TemporalConfig()` in `temporal_generator.py` and every caller relying on defaults. Tests updated: 3 tests in `test_grid.py` adjusted from 432 to 456 months.

Cross-ref: C-130 (zero-filled months indistinguishable from observations), C-129 (partition boundaries no single source of truth), C-156 (ACLED temporal range mismatch).

### ~~C-174~~: `latlon_to_pgid` silently clamps out-of-bounds coordinates

| Field | Value |
|-------|-------|
| ID | C-174 |
| Tier | 3 |
| Source | repo-assimilation (2026-05-20) |
| Trigger | Resolved 2026-05-23 |
| Location | `src/datafactory_priogrid/cell_generator.py:112-135` |

**Resolved 2026-05-23.** Fix: Replaced `np.clip` silent clamping with explicit `ValueError` + `logger.error` (ADR-008 compliance). Out-of-bounds latitudes or longitudes now raise immediately with the offending values in the error message (up to 5 shown). The downstream bounds check in `grid_compilation.py:126` is no longer dead code — invalid coordinates are caught at the source. 5 boundary tests added to `test_grid.py`: lat above 90, lat below -90, lon above 180, lon below -180, valid boundary point (89.75, 179.75).

See also C-130 (zero-fill ambiguity — same class of silent data misrepresentation).

---

### C-175: Aggregation missing-field coalesced to zero, not NaN — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-175 |
| Tier | 3 |
| Source | repo-assimilation (2026-05-20) |
| Trigger | Source removes or renames a field that a `FeatureSpec.value_field` references — e.g., UCDP renames `best` to `best_estimate` |
| Location | `src/datafactory_compilation/aggregation.py:18-19` (`sum_field`: `e.get(field, 0) or 0`), `src/datafactory_compilation/aggregation.py:28-29` (`max_field`: `e.get(field, 0) or 0`) |

`sum_field` and `max_field` aggregation strategies treat missing event fields as 0 via `e.get(field, 0) or 0`. If UCDP renames `best` to `best_estimate`, every event would contribute 0 to the `fatalities` feature — the compiled grid would contain all zeros for that column, indistinguishable from "zero events." The `count` strategy is unaffected (ignores field). The current mitigation is that `grid_compilation.py:_required_columns()` validates that `config.lat_field`, `config.lon_field`, and `config.date_field` exist in the table — but `value_field` is not validated at the column level before aggregation. Not Tier 1 because: (a) current sources have stable field names, (b) the zero-fill is consistent (every event contributes 0, so the feature is uniformly zero rather than subtly wrong). Tier 3 because: if triggered, the entire feature column is silently useless.

See also C-45 (no Parquet schema evolution), C-36 (UCDP API contract no schema versioning).

---

### C-156: ACLED temporal range mismatch — zero-fill before 2020 in assembled grid — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-156 |
| Tier | 3 |
| Source | ACLED grid verification (2026-05-06) |
| Trigger | Model uses ACLED features for pre-2020 months without awareness that values are zero-fill, not observed zeros |
| Location | `scripts/assemble_grid.py` (ACLED integration pending), `data/compiled/acled/grid.npy` |

UCDP data covers 1989–present; ACLED compiled data covers 2020–present. When ACLED features are integrated into the assembled grid alongside UCDP, months before 2020 will be zero-filled. These zeros are indistinguishable from observed months with zero events. A model training on both UCDP and ACLED features across the full 1989–present range would learn that ACLED conflict is zero before 2020 — potentially suppressing ACLED feature weights or creating a spurious structural break. This is the same class of problem as C-130 (UCDP zero-fill beyond data boundary) but on the leading edge rather than the trailing edge. Zero-fill is accepted as the initial approach; the risk is that consumers don't know about the boundary. Resolution options: (a) metadata field `acled_first_valid_month_id` in provenance/zattrs, (b) `load_dataset()` warning when ACLED features requested for pre-2020 months, (c) NaN-fill instead of zero-fill (breaks models expecting float32 without NaN handling).

See also C-130 (zero-filled future months), C-133 (zero-padding warning bypass).

---

## Tier 4 — Accept or Defer

### C-21: No characterization tests for migration source — [DEFER]
The metric lab code being migrated has its own tests, but this repo has no "golden output" tests that capture expected behavior of migrated code. Migration without characterization tests risks silent behavioral divergence. **Trigger: when views-metric-lab plans to migrate a model that depends on viewser-transformed features (currently no migration planned) (trigger rewritten during review-rr 2026-05-24).**
**Source:** Feathers
**Update 2026-04-21:** Partially addressed by M13 (verification examples suite). 15 `examples/ex_*.py` scripts verify consumer-facing API contracts end-to-end. Not full characterization tests, but covers the consumer surface model developers depend on.
Tier recalibrated from 3 to 4 during review-rr (2026-05-24). No migration imminent. Partially addressed by verification examples.

### C-121: Phase 6.4 (SSH IP restriction) is documented but unexecuted — [DEFER]
Phase 6.4 of `hetzner_deployment_guide.md` documents SSH IP restriction via Hetzner Cloud Firewall or ufw, but has never been executed end-to-end. C-87 surfaced the same pattern: Phase 6.3 was documented in March but only executed today (2026-04-10), revealing a missing `passwd` step that locked the new user out of `sudo`. The fix took 30 minutes; the bug was in the documentation since v1.0. **Lesson: untested documentation is broken documentation.** Phase 6.4 should be audited and ideally dry-run before the first real execution. **Trigger: before executing Phase 6.4 (which itself is blocked on PRIO IT CIDRs).** Resolution: walk through Phase 6.4 line-by-line, verify each command, add missing edge cases, then execute on the server.
**Source:** Lessons from C-87 incident, 2026-04-10

### C-37: `date_prec=5` semantics hardcoded — [DEFER]
`temporal_distribution.py:22` defines `_SUMMARY_DATE_PREC = 5`. If UCDP changes `date_prec` semantics, temporal distribution silently produces wrong results. No UCDP documentation exists for `date_prec` values. **Trigger: UCDP publishes a codebook or changes observed empirically.**
**Source:** Repo assimilation

### C-36: UCDP API contract has no schema versioning — [DEFER]
API envelope format and 13 `REQUIRED_FIELDS` are hardcoded in `ucdp_annual.py:43-72,176-190`. No schema version negotiation. Fail-loud catches field removals; field additions are harmless (silently preserved). Kleppmann (Ch.4 pp.131-136) notes that service providers often cannot control client upgrades, making forward compatibility essential — our fail-loud on missing fields is the correct strategy, but we have no mechanism to detect silent semantic changes in existing fields. **Trigger: UCDP announces API v2 or breaking change.**
**Source:** Repo assimilation. DDIA Ch.4 pp.112, 131-136.

### C-45: No Parquet schema evolution strategy — [DEFER]
`pa.concat_tables(promote_options="default")` in `ucdp.py:439-441` silently adds columns when UCDP adds fields. Removed fields leave nulls in new records. No schema registry. Kleppmann (Ch.4 pp.112-127) treats schema evolution as essential for long-lived data: backward compatibility (new code reads old data) and forward compatibility (old code reads new data) must both be maintained. Our `promote_options="default"` handles column additions (backward compat) but not removals or renames. Ch.4 p.125 recommends a schema versioning database; Ch.4 p.131 notes archival storage should re-encode using the latest schema. **Trigger: UCDP removes a field or renames a column.**
**Source:** Kleppmann (expert review 6). DDIA Ch.4 pp.112-127, 131.

### C-44: Harvest pipeline template is implicit — [DEFER]
All five harvesters follow config->fetch->validate->compare->archive->store->provenance but no shared template enforces step order. A new source author must read existing sources to discover the pattern. **Trigger: before V-Dem (9th source) — extract shared harvest template to reduce copy-paste per source (trigger rewritten during review-rr 2026-05-24).**
**Note (2026-04-04):** Trigger condition met — 5 sources exist (ucdp_annual, ucdp_candidate, ucdp_dot9, priogrid_static, gaul_admin). Accepted at v1.0 scope: all 5 harvesters work correctly, implicit template hasn't caused bugs. Reassess before V-Dem (6th source).
**Note (2026-05-02):** 6th source added (ACLED). Pattern was replicated from existing harvesters without issues. Template extraction deferred to V-Dem (7th source) or next refactor.
**Note (2026-05-18):** 7th source added (GHS-POP). Pattern replicated from GAUL harvester. Trigger condition met — consider template extraction at next refactor opportunity.
**Note (2026-05-19):** Full cross-layer WET inventory completed — see C-164 for patterns spanning all 4 layers, not just harvest. This concern covers the harvest template; C-164 covers the broader cross-layer picture.
**Note (2026-05-21):** C-183 merged here. Expert code review of harvest caching found that the three caching/idempotence implementations (UCDP two-tier, ACLED single-tier, GHS-POP single-tier) share the same two-key cache pattern (file exists + ledger digest) but diverge on change detection, force-refresh semantics, and outcome vocabulary. No shared contract exists — each reinvents the pattern independently. This is the caching-specific instance of the general harvest template gap. See ADR-032 (harvest idempotence) for the formalized pattern.
**Note (2026-05-22):** 8th source added (GHS-BUILT-S). Harvest pattern replicated without issues. Cross-ref C-164.
**Source:** GoF (expert review 6)

### C-46: No ledger write idempotency — [DEFER]
`append_ledger_entry()` has no dedup key. Process crash after append but before caller return causes duplicate on retry. Ledger readers tolerate duplicates. Kleppmann (Ch.12 pp.516-518) argues exactly-once semantics require idempotence via operation identifiers — each write carries a unique ID; consumers deduplicate on read. Ch.7 p.231 warns that retrying a successful-but-unacknowledged write without dedup causes silent duplication. Recommended approach: add an `operation_id` field (e.g., content digest of the entry) to each ledger record. **Trigger: consider when ledger is consumed by external systems requiring exactly-once semantics.**
**Source:** Kleppmann (expert review 6). DDIA Ch.7 p.231, Ch.12 pp.516-518.

### C-29: No end-to-end integration test — [DEFER]
Partially addressed by `test_integration.py` (100 events, realistic pipeline). Full-scale end-to-end with all 3 sources untested. **Trigger: when pipeline validation needs independent orchestration, or 2nd deployment target is set up (trigger rewritten during review-rr 2026-05-24).**
**Note (2026-04-04):** Trigger condition met — server in production at 204.168.219.108. Accepted at v1.0 scope: integration test covers the critical harvest→compile path, `verify_remote.py` validates the deployed output (10/10 checks). Reassess before V-Dem.
**Update (2026-04-26):** Test review identified specific gap: no harvest→consolidation integration test. `test_integration.py` tests the full pipeline but with synthetic events. No test verifies that actual UCDP Parquet output (column names, types, date format) is consumed correctly by `consolidate_ucdp()`. The stale-zarr incident showed that harvester changes (page_size, assertion thresholds) can produce subtly different output that breaks downstream.
**Update (2026-05-05):** ACLED compilation test review identified same gap for ACLED pipeline: no integration test connecting harvest→consolidate→viewpoint→compile. No test verifies viewpoint→compilation Parquet schema compatibility (that viewpoint output columns match what `compile_grid` expects via `date_field`, `lat_field`, `lon_field`, and filter fields). ACLED pipeline has the same structural risk as UCDP.
**Source:** Repo assimilation, Feathers, Test review 2026-04-26, ACLED compilation test review 2026-05-05

### C-70: No circuit breaker for UCDP API — [DEFER]
After `max_retries` exhaustion, harvest fails immediately. If UCDP API is down for hours, every harvest attempt exhausts retries. No "open circuit" to fail fast on known-dead endpoints. Kleppmann (Ch.7 p.231) warns that retrying overload "will make the problem worse, not better" and recommends exponential backoff with distinct handling for overload vs transient errors. Ch.8 pp.281-283 discusses timeout-based fault detection and network congestion amplification. **Trigger: implement before multi-operator or automated deployment.**
**Source:** Nygard (expert review #4). DDIA Ch.7 p.231, Ch.8 pp.281-283.

### C-72: HTTP 429 not distinguished from 500 — [DEFER]
Rate-limit responses get the same retry treatment as server errors. No `Retry-After` header parsing. `request_with_retry` fails fast on all 4xx (no retry), meaning a 429 rate-limit terminates the harvest immediately. Kleppmann (Ch.7 p.231) explicitly argues "it is only worth retrying after transient errors (e.g., deadlock, network interruption); after a permanent error, a retry would be pointless" and that overload errors need distinct handling. Ch.8 p.281 notes short timeouts risk declaring healthy services dead during load spikes. **Trigger: if UCDP or ACLED starts returning 429s during multi-page harvest (not observed to date). Impact is higher for ACLED because multi-page pagination can be long-running and all in-memory events are lost on failure.**
**Source:** Nygard (expert review #4). DDIA Ch.7 p.231, Ch.8 p.281. Updated: ACLED test review 2026-05-03.
**Location:** `src/datafactory_http/retry.py` (4xx fail-fast logic), `src/datafactory_harvester/sources/acled.py:fetch_paginated()`.

### C-74: CompilationConfig leaks strategy vocabulary — [DEFER]
Callers must know magic strings (`"count"`, `"sum_field"`, `"max_field"`) and filter dict syntax. No IDE discoverability. **Trigger: when a new developer writes a CompilationConfig and the strategy string enum is needed for IDE discoverability (trigger rewritten during review-rr 2026-05-24).**
**Note (2026-04-08):** Renamed from `sum_best`/`max_best` to `sum_field`/`max_field` to reflect configurable `value_field`. Old names registered as backward-compatible aliases.
**Source:** Ousterhout (expert review #4)

### C-75: FeatureFrame is shallow — adds validation but little abstraction — [DEFER]
8 public methods/properties wrapping numpy arrays. Each method is 1-5 lines. Callers must understand `[N, D]` vs `[N, D, S]` shapes. Acceptable for a data wrapper; monitor if callers misuse. **Trigger: when a consumer constructs FeatureFrame with wrong shape and the error message is insufficient to diagnose (trigger rewritten during review-rr 2026-05-24).**
**Source:** Ousterhout (expert review #4)

### C-78: `_place_events` hard to test in isolation — [DEFER]
100 lines of bin-assignment logic tested only indirectly through `compile_grid()`. Core algorithm (lat/lon -> pgid, date -> month_index) could be extracted into a pure function. **Update 2026-05-21 (ADR-031 review):** Renamed from `_place_events_columnar` — the old name falsely claimed columnar processing. The function receives Python lists from `.to_pylist()` and iterates row-by-row. The underlying P1 violation (`.to_pylist()` materialization) remains tracked in C-144. **Trigger: extract `compute_bin_assignments()` when compilation tests exceed 5 seconds.**
**Source:** Feathers (expert review #4), ADR-031 compliance review (2026-05-21). Cross-ref: C-144, C-74.

### C-79: Compilation/consolidation require real Parquet I/O in tests — [DEFER]
`compile_grid()` and `consolidate_ucdp()` always read from disk. No seam to inject mock reader. Tests create actual Parquet files. **Trigger: add `read_table_fn` parameter when test suite exceeds 30 seconds.**
**Source:** Feathers (expert review #4)

### ~~C-03~~: Protocol proliferation risk in synthetic module — [DEFER]
Subsumed into C-176 — module is dead (zero exports). `src/datafactory_synthetic/ARCHITECTURE.md` plans 3 Protocols before any concrete implementation. Premature abstraction. **Trigger: moot — module has no implementation.**
**Source:** GoF, Hickey

### C-115: Summary detection threshold (>= vs >) is architectural — [DEFER]
The summary event detection formula uses `best >= span` (not strict `best > span`). This threshold is documented in ADR-023 as an architectural invariant matching VIEWSER's current GED_loader0 behavior. An older VIEWSER notebook (GED_loader2) used strict `>`. If UCDP changes their summary event definition or VIEWSER reverts to strict `>`, this invariant would need updating. **Trigger: UCDP changes summary event definition or VIEWSER changes detection threshold.**
**Source:** Parity investigation 2026-04-08, notebook archaeology (GED_loader{0,1,2}.ipynb).

### C-116: No retry on remote zarr network failures — [DEFER]
`_load_grid_from_zarr` in `dataset.py` opens a remote zarr store via xarray/fsspec/aiohttp. Transient network errors (DNS timeout, TCP reset, server restart) fail immediately — no retry, no backoff. `datafactory_http.retry.request_with_retry()` exists but is designed for `requests`-based harvester calls, not the xarray/fsspec path. For consumers, a transient failure at 2am during automated training means a full pipeline retry. **Trigger: consumer reports intermittent failures loading remote data.** Cross-ref: C-70 (circuit breaker, harvester path).
**Source:** Expert review #5 (M12 investigation), Nygard perspective, 2026-04-08.

### C-117: Remote zarr downloads all spatial cells before region filter — [DEFER]
`_load_grid_from_zarr` applies temporal and feature subsetting lazily (xarray isel/variable selection), but spatial subsetting (region → pgid set) happens AFTER full grid materialization in `load_dataset`. For remote stores, this means downloading all 259,200 cells even when only ~13,000 are needed (e.g., Africa). The spatial dimension is 360x720 per time step per feature — less impactful than temporal (which IS subsetted), but still ~20x more data than needed for typical region queries. xarray does not support efficient irregular spatial selection on chunked stores without rechunking. **Trigger: consumer queries a single country over a slow connection and complains about latency.**
**Source:** Expert review #5 (M12 investigation), Kleppmann perspective, 2026-04-08.

### C-93: `_count_outcomes` mixes raw counts with derived computation — [DEFER]
`harvest_ucdp.py:_count_outcomes()` counts raw outcome categories (`cached`, `success`, `unchanged`, `failed`, `not_served`) then adds a computed `"served"` key (`len(results) - not_served`). Mixing enumeration with derivation in a counting function is a minor naming/responsibility ambiguity. **Trigger: refactor when harvest reporting logic is next modified.**
**Source:** PR #2 code review 2026-03-30

### C-96: fsspec does not auto-read `~/.netrc` — [DEFER]
fsspec's HTTPFileSystem does not read `~/.netrc` or set `trust_env=True` on its aiohttp session. xarray consumers must pass auth explicitly via `storage_options={"client_kwargs": {"auth": (user, pass)}}`. The `verify_remote.py` script reads netrc programmatically via Python's `netrc` module, but the primary consumer path (xarray + fsspec + zarr) does not benefit from it automatically. Consumer guide should provide a helper pattern. **Trigger: simplify consumer guide if fsspec adds netrc/trust_env support.**
**Source:** Falsification audit 2026-04-01 (F3)

### C-97: Basic auth + Caddy scalability ceiling at ~30-50 users — [DEFER]
Caddy's `basic_auth` stores username/bcrypt-hash pairs in a flat Caddyfile. No audit trail (who accessed what, when), no per-user rate limiting, no credential rotation, no MFA. Acceptable for a small research team (5-20 users). Breaks down at 30-50 users when credential management, audit requirements, and revocation coordination become operational burdens. Migration path: Caddy `forward-auth` directive + oauth2-proxy with institutional SSO (PRIO/Uppsala). **Trigger: before consumer count exceeds 30, or before institutional audit/compliance requirements emerge.**
**Source:** Falsification audit 2026-04-01 (F2)

### C-135: No runtime type validation for zarr `.zattrs` values — [DEFER]
`ds.attrs.get("last_valid_month_id")` in `dataset.py` is type-annotated as `int | None` but no runtime check validates the type. `health.py` applies `int(last_valid)` which would raise `ValueError` on a non-numeric string but silently truncate a float. The attrs are written by our own `export_zarr.py` (which produces correct types), so the only risk vector is manual server-side editing of `.zattrs`. **Trigger: manual edit of `.zattrs` on Hetzner server sets a zarr attribute to an unexpected type.**

**Location:** `src/datafactory_query/dataset.py:157-159`, `src/datafactory_provenance/health.py:179-182`.
**Source:** Tech-debt-cleanup audit (2026-04-22). Cross-ref: C-130 (zero-padding metadata).

### C-136: `read_last_entries()` crashes on non-UTF8 ledger files — [DEFER]
`read_last_entries()` in `health.py:39` calls `ledger_path.read_text()` which raises `UnicodeDecodeError` on binary-corrupted JSONL files. Since `report_ledger()` and `check_health.py` depend on this function without a try/except, a single corrupted byte in any ledger file crashes the entire health check. The ledger files are append-only JSONL written by `append_ledger_entry()` which always writes valid UTF-8, so the only risk vector is disk corruption or an external process writing binary data to the ledger path. Discovered by Red test `TestReportLedgerRed::test_binary_garbage_in_ledger`. **Trigger: disk corruption or misconfigured log rotation appends binary data to a JSONL ledger file.**

**Location:** `src/datafactory_provenance/health.py:39` (`read_text()` call).
**Resolution:** Wrap `read_text()` in try/except `UnicodeDecodeError`, or use `read_bytes().decode(errors="replace")`.
**Source:** Test review gap implementation (2026-04-22). Cross-ref: C-131, C-132 (operational monitoring).

### C-147: No pipeline orchestrator in repository — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-147 |
| Tier | 4 |
| Source | repo-assimilation (2026-04-30) |
| Trigger | When a new operator runs the pipeline for the first time without reading documentation, or when a 2nd deployment target is set up |
| Location | `scripts/` directory (19 scripts, no ordering definition) |

The pipeline is executed via individual scripts called in sequence: `harvest_ucdp.py` → `consolidate_ucdp.py` → `build_viewpoint.py` → `compile_grid.py` → `assemble_grid.py` → `export_zarr.py`. No Makefile, DAG definition, or workflow file in the repository defines or enforces this order. Correct sequencing depends on operator knowledge or reading CLAUDE.md. Each script validates its inputs exist (raises `FileNotFoundError`), so running out of order produces a clear error rather than silent corruption. `check_health.py` detects staleness after the fact. The server deployment uses cron under `views-deploy` (single `refresh_pipeline.sh` script). Currently mitigated by fail-loud input validation and single-operator deployment.

See also C-131 (no cron monitoring), C-29 (no e2e integration test).

### C-148: Hardcoded Hetzner server IP in `defaults.py` — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-148 |
| Tier | 4 |
| Source | repo-assimilation (2026-04-30) |
| Trigger | When the Hetzner server migrates to a new IP or hostname |
| Location | `src/datafactory_query/defaults.py:38` (`RemoteConfig.server = "204.168.219.108"`) |

The remote server IP `204.168.219.108` is hardcoded as the default in `RemoteConfig`. Consumer code and verification scripts (`verify_remote.py`) reference this constant. The frozen dataclass allows overrides (`RemoteConfig(server="new-ip")`), but the package-level default is embedded. A server migration requires a version bump and re-install for all consumers using the default. Single constant, trivial to update.

### C-153: ACLED API has no TotalCount — silent truncation undetectable — [OPEN]

| Field | Value |
|-------|-------|
| ID | C-153 |
| Tier | 3 |
| Source | ACLED test review (2026-05-03) |
| Trigger | ACLED API starts enforcing server-side result caps or query complexity limits that return partial data within a single page |
| Location | `src/datafactory_harvester/sources/acled.py:fetch_paginated()`, `docs/ADRs/027_harvest_count_verification.md` |

The ACLED API response envelope has `"count": null, "total_count": null` — there is no server-reported total to verify pagination completeness. The harvester terminates on empty/short pages (correct behavior for complete pagination) but cannot detect if the API silently caps results within a page. Unlike UCDP (which provides `TotalCount`), there is no way to verify "did I get everything?" without an independent count source. ADR-027 documents this as an accepted limitation with the short-page heuristic as the only available detection signal. Not Tier 1/2 because: (a) short-page heuristic catches most truncation, (b) documented in ADR-027, (c) no evidence truncation occurs in practice. Medium because: if it does occur, downstream models train on incomplete data with no error signal.

See also C-72 (HTTP 429 not distinguished), C-45 (no schema evolution strategy).

### C-154: ACLED_FEATURES config duplicated between script and tests — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-154 |
| Tier | 4 |
| Source | ACLED compilation test review (2026-05-05) |
| Trigger | Developer changes an event_type filter value in `scripts/compile_acled.py` but not in the test fixture `ACLED_FEATURES` |
| Location | `scripts/compile_acled.py` (lines 97-125), `tests/test_acled_compilation.py` (lines 29-59) |

The `ACLED_FEATURES` tuple in `tests/test_acled_compilation.py` is a copy-paste of the feature configuration in `scripts/compile_acled.py`. They are not shared — the script is not importable as a module (it uses `if __name__ == "__main__"` with `sys.exit(main())`). If a developer updates a filter value (e.g., renames `"Battles"` to `"Armed clashes"` to track an ACLED codebook change) in the script but not the test, the per-type column would silently produce zeros in production while the test still passes against its own stale fixture. Tier 4 because: (a) single-developer project, (b) filter values come from ACLED's codebook which rarely changes, (c) the `test_feature_names_match_adr028` test would catch name changes but not filter value changes.

See also C-29 (no integration test), C-74 (strategy vocabulary).

### C-155: No shared visual audit framework — per-source scripts are idiosyncratic — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-155 |
| Tier | 4 |
| Source | ACLED grid verification (2026-05-06), GHS-BUILT-S visual audit falsification (2026-05-22) |
| Trigger | 5th data source (V-Dem or WDI) requires a 5th bespoke verify script — extraction cost then exceeds duplication cost |
| Location | `scripts/visualize_audit.py` (UCDP), `scripts/verify_acled_grid.py` (ACLED), `scripts/verify_ghspop_grid.py` (GHS-POP), `scripts/verify_ghsbuilts_grid.py` (GHS-BUILT-S), `scripts/viz_style.py` (shared aesthetics only) |

Each data source has its own plotting/audit script with duplicated structural patterns: `PrecomputedData` dataclass, single-pass `precompute()`, `cell_to_label()`, `REGION_BOUNDS`, per-plot functions, and statistical pass/fail checks. The scripts share `viz_style.py` for aesthetic constants and helpers (`spatial_imshow`, `style_ax`, `save_plot`) but nothing for plot structure, check logic, or report generation.

**Note (2026-05-20):** Trigger condition met — GHS-POP is the third visual audit script. The three scripts share structural patterns but differ in domain-specific checks (population density vs. fatality rates vs. event counts). Accepted for now: three scripts is enough to see the abstraction clearly, but the abstraction is moderate complexity (pluggable feature specs, check definitions, report generation). Consider extraction when 4th source arrives. Cross-ref: C-164 (WET inventory).
**Note (2026-05-22):** GHS-BUILT-S added as 4th data source. Falsification audit proved total absence of visual audit capability — 5/5 probes hard-falsified. Escalated from Tier 4 DEFER to Tier 2.
**Note (2026-05-22):** C-155 remediated — `verify_ghsbuilts_grid.py` created (10 plots, 6 statistical checks), `--verify` flag added to pipeline, falsification stubs F1-F3 flipped. Full pipeline run successful with all checks PASS. Demoted back to Tier 4 DEFER — the original idiosyncrasy concern (4 bespoke scripts) remains but is not acute. Reassess at 5th source.

**Note (2026-05-24, repo-assimilation v1.2.20):** Quantified: 4 verification scripts total 2,804 lines (UCDP 1,015, GHS-POP 811, GHS-BUILT-S 978, ACLED not counted separately). ~60% structural overlap across scripts (`PrecomputedData` dataclass, `precompute()`, `cell_to_label()`, `REGION_BOUNDS`, per-plot functions, statistical pass/fail checks). At source #5, the extraction cost (~2 days) will be less than the duplication cost (~1 day per copy + ongoing maintenance).

See also C-44 (harvest pipeline template — same WET-before-DRY decision), C-154 (ACLED feature config duplication), C-164 (cross-layer WET inventory), C-195 (falsification test accumulation).
### C-164: Cross-layer WET debt — 4 sources replicate patterns across all 4 layers — [TRIGGER FIRED]

| Field | Value |
|-------|-------|
| ID | C-164 |
| Tier | 3 |
| Source | WET-before-DRY audit (2026-05-19), GHS-POP Phase 4 completion |
| Trigger | **Fired 2026-05-22:** 4th data source (GHS-BUILT-S) copied all 6 cross-layer patterns. Reassess before 5th source (V-Dem or WDI). |
| Location | All `src/datafactory_*` packages — see inventory below |

With 4 sources implemented (UCDP, ACLED, GHS-POP, GHS-BUILT-S), the codebase has accumulated intentional WET patterns across all four layers. The WET-before-DRY strategy (ADR: write 3 times before abstracting) has succeeded — concrete patterns are now clear. The 4th source (GHS-BUILT-S, v1.2.20) copied all patterns again, confirming the abstraction boundaries.

**Inventory of cross-layer WET patterns:**

1. **Harvester config validation** (5 files): `timeout >= 1`, `page_size >= 1`, `max_retries >= 1`, year range validation — all follow identical `if val < 1: raise ValueError` patterns. Files: `ucdp_annual.py`, `ucdp_candidate.py`, `ucdp_dot9.py`, `acled.py`, `ghspop.py`. Abstraction: trivial (shared validators or base config).

2. **Consolidation helpers** (2 files): `_build_harvest_index()`, `_get_harvest_metadata()`, and `_tag_table()` are line-by-line identical between `consolidators/ucdp.py` and `consolidators/acled.py`. Only dedup key construction differs. Abstraction: trivial-moderate (extract shared functions, parameterize dedup key).

3. **Viewpoint builder scaffolding** (3 files): Config-or-shortcut pattern, file existence check, provenance recording, ViewpointResult construction — structurally identical across `acled_v1.py`, `ghspop_v1.py`, and `ucdp_v1.py` (via `builders/ucdp_v1.py`). Core logic differs (event filtering vs. spatial aggregation). Abstraction: moderate (base builder class with template method).

4. **Compilation output writing** (2 files): `grid.npy`, `pgids.npy`, `time_steps.npy`, `feature_names.json`, `provenance.json` — identical output generation code in `grid_compilation.py` and `pregridded_compilation.py`. Input logic is fundamentally different (lat/lon events vs. pgid/month_id rows). Abstraction: moderate (extract `_write_grid_output()` helper).

5. **`_VIEWS_EPOCH_YEAR = 1980`** (2 files): Duplicated in `ghspop_v1.py` and `pregridded_compilation.py`. Already defined as `_VIEWS_EPOCH` in `temporal_generator.py`. Abstraction: trivial (import from single source).

6. **Provenance recording** (~48 call sites): `append_ledger_entry()` called with structurally similar dicts across all layers. Common fields: dataset, outcome, ledger_version, digest_algorithm. Source-specific fields vary. Abstraction: trivial-moderate (builder pattern for ledger dicts). See also C-06.

7. **Pipeline runner scripts** (3 files): `run_ucdp_pipeline.py`, `run_ghspop_pipeline.py`, `run_ghsbuilts_pipeline.py` replicate the same orchestration pattern (~846 lines combined): argparse setup, `--skip-to` logic, sequential step execution with log headers. Core logic varies (which steps to run, source-specific paths). Abstraction: moderate (shared runner with pluggable step definitions).

8. **Harvest script wrappers** (7 files): `harvest_ucdp.py`, `harvest_acled.py`, `harvest_ghspop.py`, `harvest_ghsbuilts.py`, `harvest_priogrid.py`, `harvest_gaul.py`, `harvest_candidates.py` are thin ~150-line wrappers (~1,035 lines combined) that parse args and call the harvester function. Structurally identical. Abstraction: trivial (shared `harvest_main()` wrapper with source config).

**Recommended abstraction order** (by ROI when 5th source arrives):
1. `_VIEWS_EPOCH_YEAR` constant dedup (trivial, 5 min)
2. Compilation output writer extraction (moderate, prevents most duplication)
3. Harvest script wrappers (trivial, 7 near-identical files)
4. Harvester config validators (trivial, prevents 5→6+ duplication)
5. Pipeline runner shared infrastructure (moderate, 3 files with shared arg/step pattern)
6. Consolidation shared helpers (moderate, 3 near-identical functions)
7. Viewpoint builder base class (moderate, highest design risk)

Cross-ref: C-44 (harvest pipeline template), C-07 (frozen dataclass pattern), C-155 (visual audit framework), C-06 (provenance composability).

**Note (2026-05-22):** Trigger fired — GHS-BUILT-S (8th source, 4th raster) copied all 6 patterns. `ghsbuilts_v1.py` duplicates `_read_geotiff`, `_aggregate_with_alignment`, `_interpolate_temporal` from `ghspop_v1.py`. `_VIEWS_EPOCH_YEAR` now duplicated in 3 files. Accepted for v1.2.20; extract shared raster utilities before 5th source (V-Dem or WDI).

**Note (2026-05-24, tech-debt-cleanup investigation):** Quantified each pattern for extraction planning:

| # | Pattern | Identical lines | Files | Extraction risk | Notes |
|---|---------|----------------|-------|----------------|-------|
| 1 | Harvester config validators | 36 (12×3 UCDP) | 5 | Safe | `page_size`, `max_retries`, `timeout` checks |
| 2 | `_tag_table()` | 34 | 2 | Safe | 100% copy-paste; zero domain variance |
| 3 | Viewpoint scaffolding | 35 | 4 | Moderate | Config-or-shortcut + provenance; tightly coupled to config classes |
| 4 | Compilation output writer | 30 | 2 | Safe | Only diff: pregridded adds 3 diagnostic fields to ledger dict |
| 5 | `_VIEWS_EPOCH_YEAR` | 2 | 3 (ghspop_v1, ghsbuilts_v1, pregridded imports correctly) | Safe | Trivial: replace private copies with import |
| 6 | Provenance recording | ~48 call sites | all layers | Moderate | Deferred — C-06 tracks this |
| 7 | Pipeline runners `--skip-to` | 80-120 | 3 | Moderate | Step index handling, timing, fallback validation |
| 8 | Harvest script wrappers | 200-250 | 7 | Moderate | argparse + timing + banner boilerplate |

Raster-specific functions confirmed identical copy-paste between `ghspop_v1.py` and `ghsbuilts_v1.py`:
- `_read_geotiff()`: 39 lines identical (pure I/O, no domain coupling)
- `_interpolate_temporal()` + `_interp_step()` + `_interp_linear()`: 103 lines identical (pure data transformation)
- `_aggregate_with_alignment()`: 74 lines each, **NOT identical** — ghspop has nodata masking (float32, `strip[(strip == nodata) | (strip < 0.0)] = 0.0`), ghsbuilts has no masking (uint32, no nodata sentinel). Domain-justified divergence — **do not extract**.

**Total confirmed-safe extraction candidates: ~340 lines across patterns 1-5 + raster functions. Total deferred: ~530 lines across patterns 3, 6-8 (moderate risk or larger refactor scope).**

**v1.2.21 extractions completed (2026-05-25):**
- Pattern #2 resolved: `_tag_table()` extracted to `datafactory_consolidation/tagging.py` (Task 6)
- Pattern #4 resolved: compilation output writer extracted to `datafactory_compilation/output.py` (Task 7)
- Pattern #5 resolved: `VIEWS_EPOCH_YEAR` moved to `datafactory_provenance/constants.py` (Task 3)
- Raster I/O resolved: `_read_geotiff()` extracted to `datafactory_viewpoint/raster_io.py` (Task 4)
- Temporal interpolation resolved: `_interpolate_temporal()`, `_interp_step()`, `_interp_linear()`, `VALID_TEMPORAL_INTERPOLATIONS` extracted to `datafactory_viewpoint/temporal.py` (Task 5)
- Remaining: patterns 1 (harvester config validators), 3 (viewpoint scaffolding), 6 (provenance recording), 7 (pipeline runners), 8 (harvest wrappers) deferred to next cycle.

**Source:** WET-before-DRY inventory audit after GHS-POP Phase 4 completion (2026-05-19), updated GHS-BUILT-S (2026-05-22), tech-debt-cleanup investigation (2026-05-24), v1.2.21 maintenance sprint (2026-05-25).

### ~~C-169: 2 CI tests fail due to missing infrastructure — permanent UNSTABLE~~ RESOLVED

| Field | Value |
|-------|-------|
| ID | C-169 |
| Tier | 4 |
| Source | PR #53 review (2026-05-20) |
| Trigger | Real test regression is introduced but masked by permanent UNSTABLE status, causing a broken build to be merged |
| Location | `tests/test_query.py::test_remote_zarr_has_last_valid_month_id` (requires `.netrc` for server auth), `tests/test_consumer_data.py::test_at_least_one_model_found` (requires `../views-models/` sibling repo) |

Two tests consistently fail in CI because they require infrastructure the CI runner doesn't have: (1) `test_remote_zarr_has_last_valid_month_id` gets HTTP 401 because CI has no `.netrc` with server credentials; (2) `test_at_least_one_model_found` gets `FileNotFoundError` because CI has no `../views-models/` checkout. Both pass locally on the development machine. The permanent failures make `mergeStateStatus: UNSTABLE` the baseline, so real regressions are invisible in the CI signal. Resolution options: (a) mark these tests with `@pytest.mark.skipif` when CI environment detected, (b) mock the external dependencies, (c) move them to a separate `tests/integration/` directory excluded from CI.

**Resolved 2026-05-25 (v1.2.21 Task 2):** Added `@pytest.mark.skipif` guards for both infra-dependent tests. CI signal restored — `uv run pytest` now passes with 0 FAILED, 0 ERROR.

Cross-ref: C-96 (fsspec netrc), C-29 (no e2e integration test).

### C-181: UCDP candidate/dot9 discovery probes API even when all versions cached — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-181 |
| Tier | 4 |
| Source | Expert code review of harvest caching (2026-05-21) |
| Trigger | UCDP rate-limits or blocks IP after repeated full-range discovery probes on every pipeline run |
| Location | `src/datafactory_harvester/sources/ucdp_candidate.py:146-200` (`discover_versions`), `src/datafactory_harvester/sources/ucdp_dot9.py:132-182` (`discover_dot9_versions`) |

Both candidate and dot9 harvesters probe the UCDP API month-by-month from `start_year`/`start_month` until a version returns no data. With data from Jan 2018 onward, this is 98+ API calls per harvest run — even when every version is already cached locally. The probes are small (pagesize=1) but still hit the API on every run. The caching check happens _after_ discovery: `_fetch_version` skips download for cached versions, but `discover_versions` always probes the full range. A discovery cache (persist known versions to disk, only probe beyond the last known month) would reduce 98+ calls to 1-3. Tier 4 because: (a) UCDP has not rate-limited us, (b) each probe is tiny, (c) the cost is latency (~2 min) not correctness.

Cross-ref: D-26 (discovery probing cost vs cache staleness), C-44 (harvest pipeline template).

### C-185: GHS-POP epoch caching has no digest comparison — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-185 |
| Tier | 4 |
| Source | Expert code review of harvest caching (2026-05-21) |
| Trigger | JRC silently updates a GeoTIFF epoch at the same URL without changing the filename |
| Location | `src/datafactory_harvester/sources/ghspop.py:140-164` (`_fetch_epoch` cache check) |

GHS-POP uses single-tier caching: file exists + ledger has digest → skip. Unlike UCDP candidate/dot9, there is no post-fetch digest comparison that would detect if the remote file changed. This is architecturally appropriate for GHS-POP because JRC releases are immutable (a new epoch gets a new URL, not a replacement file). However, if JRC ever silently replaces a file, the harvester would not detect it. Tier 4 because: (a) JRC releases are versioned and immutable by convention, (b) the risk is hypothetical, (c) a digest comparison would require re-downloading a 450 MB ZIP to compare.

Cross-ref: C-184 (ACLED same weakness), D-27 (two-tier vs single-tier cache), C-44 (harvest pipeline template).

### C-109: Advisory file locks (fcntl) don't work across NFS — [DEFER]
`file_lock()` in `digests_and_ledgers.py` uses `fcntl.flock` which is advisory and may not work on network filesystems (NFS, CIFS). Currently deployed on local SSD on the Hetzner server. A migration to shared/network storage would silently break concurrency protection for ledger writes. Kleppmann (Ch.7 pp.234-236) describes read-committed isolation via locks — our fcntl.flock achieves this at the file level on local disk. Ch.8 pp.301-303 introduces fencing tokens as a safety mechanism when locks can be stale: a monotonically increasing token ensures an expired lock holder cannot perform writes. This pattern would be needed if we migrate to network storage. **Trigger: verify lock behavior before migrating to network-attached storage or multi-server deployment.**
**Source:** Repo assimilation 2026-04-04 (Phase 5, invariant 10). DDIA Ch.7 pp.234-236, Ch.8 pp.301-303.

### ~~C-176: `datafactory_synthetic` is a dead module with zero exports~~ RESOLVED

| Field | Value |
|-------|-------|
| ID | C-176 |
| Tier | 4 |
| Source | repo-assimilation (2026-05-20) |
| Trigger | When synthetic data generation is needed for a consumer or test infrastructure |
| Location | `src/datafactory_synthetic/__init__.py` (empty `__all__`), `pyproject.toml:46` (declared in wheel) |

`datafactory_synthetic` is declared in `pyproject.toml` as a wheel package, tested for `__all__` existence in `test_package_structure.py`, and subject to import enforcement in `test_import_enforcement.py` — but exports nothing and is imported by nothing. The `ARCHITECTURE.md` inside the package plans 3 Protocols before any implementation (see C-03). The module occupies a slot in the dependency DAG and test infrastructure while providing zero functionality. Tier 4 because: no correctness or reliability impact; single-developer scope.

**Resolved 2026-05-25 (v1.2.21 Task 9):** Entire `src/datafactory_synthetic/` directory deleted. Removed from `pyproject.toml` packages list, `test_package_structure.py`, `test_import_enforcement.py`, 5 ADRs, 7 ARCHITECTURE.md files, and README.md. `uv sync` confirmed clean uninstall.

See also C-03 (protocol proliferation — moot since module has no implementation; C-03 subsumed into this entry).

---

### C-159: ACLED snapshot archiving and revision comparison paths untested — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-159 |
| Tier | 4 |
| Source | ACLED test review (2026-05-07) |
| Trigger | When `archive_snapshot` or `compare_snapshots` behavior changes in a refactor, or when snapshot archiving logic is implicated in a data integrity incident |
| Location | `src/datafactory_harvester/sources/acled.py:476-490` (`compare_snapshots` and `archive_snapshot` calls in `_fetch_single_year`) |

`_fetch_single_year` compares the new fetch against the previous snapshot (via `compare_snapshots`) and archives the old snapshot before saving the new one (via `archive_snapshot`). Neither branch is exercised in `test_acled_harvester.py`. The `force_refresh` test creates a valid previous Parquet so it exercises the `compare_snapshots` path, but does not assert on the comparison result or archiving behavior. Both functions are tested in their own modules, so the risk is limited to integration wiring.

See also C-44 (harvest pipeline template — shared archiving pattern).

### C-160: ACLED `fetch_paginated` string-data corruption has no guard — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-160 |
| Tier | 4 |
| Source | ACLED test review (2026-05-07) |
| Trigger | ACLED API returns a string instead of a list for the `data` field, or returns a non-iterable type |
| Location | `src/datafactory_harvester/sources/acled.py:347` (`all_events.extend(results)` where `results = data.get("data", [])`) |

`test_api_returns_non_list_data_silently_corrupts` documents that if the API returns `"data": "abc"`, `extend()` iterates characters and `events == ["a", "b", "c"]`. This is caught by downstream `validate_events` (field presence check), but the fetch layer itself has no type guard. The UCDP harvester has the same pattern. Accepted: validation catches it, and adding a type guard here would be defense-in-depth (not load-bearing). Cross-ref: C-153 (no TotalCount for truncation detection).

### C-173: Hetzner CPX32 has no swap — OOM kills with zero safety net — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-173 |
| Tier | 3 |
| Source | Falsification audit + 8-expert code review (2026-05-20) |
| Trigger | Any transient memory spike above physical RAM during pipeline execution on the Hetzner server |
| Location | Hetzner CPX32 server configuration, `docs/guides/hetzner_deployment_guide.md` (troubleshooting section) |

The Hetzner CPX32 (8 GB RAM) has no swap partition or swapfile. Without swap, the Linux OOM killer is the only backstop — any process that exceeds available RAM is killed immediately (exit code 137) with no chance to degrade gracefully. The GHS-POP viewpoint loads a 6.88 GiB GeoTIFF array, leaving ~600 MB headroom for Python, tifffile buffers, and OS services. A 2 GB swapfile would convert hard kills into degraded performance. Swap setup documented in deployment guide troubleshooting section (v1.2.18). Cross-ref: C-165 (original OOM), C-170 (list accumulation OOM), C-88 (server hardening).

### C-184: ACLED `_year_is_cached` checks file existence, not file integrity — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-184 |
| Tier | 3 |
| Source | Expert code review of harvest caching (2026-05-21) |
| Trigger | Truncated or corrupted Parquet file on disk (e.g., disk full during write, partial download) with a valid ledger digest |
| Location | `src/datafactory_harvester/sources/acled.py:435-443` (`_year_is_cached`) |

`_year_is_cached` checks two conditions: (1) file exists on disk, (2) ledger has a digest for this version. Neither condition verifies that the file's content matches the ledger digest. A truncated Parquet (e.g., from a disk-full condition during write) would pass both checks and be served downstream. The UCDP candidate/dot9 harvesters have a stronger pattern: they compute the actual file digest and compare it against the ledger digest, which catches corruption. GHS-POP has the same weakness (C-185). The fix is to compute `compute_file_digest(snap_path)` and compare against `last_digest_for_version()`. Tier 3 because: (a) requires a specific failure mode (disk full during write), (b) downstream Parquet readers would likely raise on a truncated file, providing a secondary signal.

Cross-ref: C-182 (`last_digest_for_version` accepts failed entries), C-185 (GHS-POP same weakness), C-44 (harvest pipeline template).

### C-186: Shapefile harvester lacks outcome vocabulary; ADR-032 overstates compliance — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-186 |
| Tier | 3 |
| Source | Falsification audit round 2 of PR #59 (2026-05-21) |
| Trigger | Developer implements a new harvester by following ADR-032's "all harvesters record failed entries" claim and relies on that assumption for the shapefile harvester path |
| Location | `src/datafactory_priogrid/shapefile_harvester.py:120-167` (fetch/extract logic, no try/except), `docs/ADRs/032_harvest_idempotence.md:141` (false claim) |

The shapefile harvester (`shapefile_harvester.py`) predates the outcome vocabulary introduced for C-182. Its ledger entries use `"changed": True/False` instead of `"outcome": "success"/"unchanged"/"failed"`. There is no try/except around the fetch/extract path, so failures write no ledger entry at all. This is not a correctness bug — entries without an `outcome` field are accepted by backward compatibility, and the absence of a failed entry means the next run will re-fetch. However, ADR-032 Implementation Notes claim "All harvesters record 'failed' entries in except handlers before re-raising," which is false for this harvester. Additionally, ADR-032 mentions `last_digest_for_version` 6 times but `last_digest` (the non-versioned sibling) 0 times — UCDP annual (`ucdp_annual.py:339`) and the shapefile harvester (`shapefile_harvester.py:137`) use `last_digest`, not `last_digest_for_version`. Tier 3 because: (a) no silent corruption (backward compat handles it), (b) the ADR false claim affects future developers reading the contract, (c) the harvester has zero failure observability in the ledger.

Cross-ref: C-44 (harvest pipeline template), C-184 (ACLED same structural gap), C-185 (GHS-POP same gap), ADR-032.

### C-189: GHS-BUILT-S test coverage parity gap — 19% of combined other sources

| Field | Value |
|-------|-------|
| ID | C-189 |
| Tier | 3 |
| Source | Falsification audit — coverage parity (2026-05-22) |
| Trigger | GHS-BUILT-S encounters a production incident on Hetzner that would have been caught by Red-team or falsification tests present for GHS-POP but absent for GHS-BUILT-S |
| Location | `tests/test_ghsbuilts_harvester.py`, `tests/test_ghsbuilts_viewpoint.py`, `tests/test_ghsbuilts_compilation.py`; parity stubs in `tests/test_falsification_ghsbuilts_coverage_parity.py` |

GHS-BUILT-S test suite has 41 test functions vs 215 for ACLED + GHS-POP + PRIO-GRID/GAUL combined (19%). Five specific gaps: (F1) 41 vs 215 test functions, (F2) 86 vs 368 assertions, (F3) 1 vs 10 Red-team classes — viewpoint and compilation have zero adversarial tests, (F4) 0 vs 7 dedicated falsification test files — GHS-POP has 4 (deploy v1/v2/v3, memory), (F5) viewpoint tests are 441 lines vs GHS-POP viewpoint alone at 937 lines. Root cause: WET-before-DRY replication correctly duplicated production code but not the accumulated test and audit investment from GHS-POP's five PRs and four OOM-fix cycles. Parity stubs are `xfail strict=True` and will break when thresholds are met.

Cross-ref: C-164 (WET-before-DRY raster code duplication), C-180 (no falsification tests for non-GHS-POP compilation/viewpoint paths).

### ~~C-190~~: KNOWN_GLOBAL_BUILT_AREA reference values ~6-7x actual JRC totals — [RESOLVED]

| Field | Value |
|-------|-------|
| ID | C-190 |
| Tier | 4 |
| Source | GHS-BUILT-S visual audit run (2026-05-22) |
| Trigger | Epoch ratio check used as automated pass/fail gate (e.g., CI assertion on ratio < 2.0) instead of current advisory role |
| Location | `scripts/verify_ghsbuilts_grid.py:47-62` (`KNOWN_GLOBAL_BUILT_AREA` dict) |

**Resolved 2026-05-23.** Root cause: the original `KNOWN_GLOBAL_BUILT_AREA` values were approximate guesses (~74B for 2020), not verified against JRC's published BUTOT statistics or the raw GeoTIFF pixel sums (~465B for 2020). Empirical confirmation: raw pixel sums for all 12 epochs computed from GHS_BUILT_S R2023A 30ss GeoTIFFs; grid epoch totals match raw sums to ratio 1.0000. Fix: replaced reference values with raw pixel sums, added `built_area_vs_jrc` boolean check (0.85–1.15 tolerance, matching GHS-POP's `pop_sanity_vs_known` pattern), tightened ratio display threshold from 0.5–2.0 to 0.85–1.15. All 7 checks now PASS.

Cross-ref: C-155 (visual audit framework).

### ~~C-191~~: `refresh_pipeline.sh` has no GHS-BUILT-S steps — feature dead on arrival in production

| Field | Value |
|-------|-------|
| ID | C-191 |
| Tier | 2 |
| Source | Falsification audit — merge-readiness (2026-05-23) |
| Trigger | Resolved 2026-05-23 |
| Location | `scripts/refresh_pipeline.sh`, `scripts/harvest_ghsbuilts.py` (created), `docs/guides/hetzner_deployment_guide.md` |

**Resolved 2026-05-23.** Fix: Created `scripts/harvest_ghsbuilts.py` (thin harvest script matching `harvest_ghspop.py` pattern). Added GHS-BUILT-S to `refresh_pipeline.sh`: harvest step (Step 1), compile step (new Step 7: `run_ghsbuilts_pipeline.py --skip-to viewpoint`), `--ghsbuilts-grid` flag to assembly (Step 8). Renumbered all steps from 10 to 11. Updated header comments. Added GHS-BUILT-S paragraph to `hetzner_deployment_guide.md` covering ~2 GB download, ~3 min harvest, ~5 min viewpoint, no credentials, ADR-034 (no consolidation). Falsification stubs in `tests/test_falsification_ghsbuilts_merge_ready.py` all pass. Automated enforcement via `tests/test_operational_integration.py` (C-192 fix) prevents recurrence.

See also C-147 (no pipeline orchestrator), C-192 (recurring workflow gap, resolved).

### ~~C-192~~: Operational integration consistently trails implementation — 3rd recurrence

| Field | Value |
|-------|-------|
| ID | C-192 |
| Tier | 3 |
| Source | Falsification audit — merge-readiness pattern analysis (2026-05-23), user observation |
| Trigger | Resolved 2026-05-23 |
| Location | `tests/test_operational_integration.py` (created), `scripts/refresh_pipeline.sh`, `docs/guides/hetzner_deployment_guide.md` |

**Resolved 2026-05-23.** Recurring bug class: operational integration trailed code implementation three times (GHS-POP CIC drift, GHS-POP deployment guide, GHS-BUILT-S refresh_pipeline.sh + deployment guide). The post-mortem checklist (`reports/pre_deploy_post_mortem.md:176-188`) was not consulted during GHS-BUILT-S — items 9-10 missed again.

Fix: Created `tests/test_operational_integration.py` — a generic enforcement test that reads `PIPELINE_SOURCES` from the source registry and verifies every grid-producing source appears in both `refresh_pipeline.sh` and `hetzner_deployment_guide.md`. This converts post-mortem checklist items 9-10 into automated tests. When the 5th source (V-Dem or WDI) is added to `PIPELINE_SOURCES`, the test fails immediately if operational integration is missing. The enforcement is registry-driven — no manual updates to the test are needed.

See also C-44 (harvest pipeline template), C-147 (no pipeline orchestrator), C-157 (ACLED documentation drift, resolved), C-191 (specific GHS-BUILT-S instance, resolved).

### C-177: `_aggregate_to_prio_grid` holds source + copy simultaneously (ADR-031 P3) — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-177 |
| Tier | 4 |
| Source | ADR-031 compliance review (2026-05-21) |
| Trigger | When `_aggregate_to_prio_grid` is re-activated for a new data source or the function is called outside the builder's strip-based path |
| Location | `src/datafactory_viewpoint/builders/ghspop_v1.py:263` (`clean = data.copy()`) |

`_aggregate_to_prio_grid` creates a full copy of the input array (`clean = data.copy()`) to replace nodata with 0.0. For a 43200x86400 float32 array (~14 GiB), this doubles peak memory — a direct ADR-031 P3 violation ("never hold source and copy simultaneously at scale"). The function is no longer called from `build_ghspop_v1` (v1.2.18 switched to unconditional `_aggregate_with_alignment`), but it is retained because 7 tests exercise it directly. A docstring warning has been added (v1.2.18). If the function is ever re-activated, it must be rewritten to use in-place nodata replacement.

Tier recalibrated from 3 to 4 during review-rr (2026-05-24). Dead function, single developer, docstring warning. D-25 tracks the design question.

Cross-ref: C-170 (GHS-POP list accumulation OOM, resolved), C-173 (no swap on Hetzner).

### C-179: Consolidation dedup uses `.to_pylist()` + Python set (ADR-031 P1) — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-179 |
| Tier | 4 |
| Source | ADR-031 compliance review (2026-05-21) |
| Trigger | When consolidated store exceeds ~5M rows on an 8 GB machine |
| Location | `src/datafactory_consolidation/consolidators/ucdp.py:451-458`, `src/datafactory_consolidation/consolidators/acled.py:283-291` |

Both UCDP and ACLED consolidators extract 4 columns via `.to_pylist()` and build Python sets for deduplication. At ~2.3M UCDP rows this is ~260 MB (manageable). The pattern is a P1 violation (columnar Arrow → row-oriented Python objects). PyArrow's `pc.is_in()` + `pc.filter()` would accomplish dedup without materialization. Deferred: current data volume fits comfortably, and consolidation runs infrequently.

Cross-ref: C-145 (viewpoint full store load), C-144 (compilation to_pydict).

### C-180: No falsification tests for non-GHS-POP compilation/viewpoint paths — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-180 |
| Tier | 4 |
| Source | ADR-031 compliance review (2026-05-21) |
| Trigger | When a memory regression is introduced in the UCDP or ACLED compilation/viewpoint path |
| Location | `tests/test_falsification_ghspop_memory.py` (GHS-POP only; no equivalent for UCDP/ACLED) |

The GHS-POP memory falsification tests (`test_falsification_ghspop_memory.py`) use AST analysis to verify structural memory safety properties (e.g., `del` targets, no `.to_pylist()`, maxworkers=1). No equivalent tests exist for UCDP viewpoint (`ucdp_v1.py`), ACLED viewpoint (`acled_v1.py`), or grid compilation (`grid_compilation.py`). Memory regressions in those paths would not be caught by the falsification framework. Deferred: the GHS-POP path is the only one that currently operates near the memory ceiling.

Cross-ref: C-144 (grid_compilation to_pydict), C-145 (viewpoint full store load), C-178 (compute_content_digest).

### D-23: ADR-031 P1 — strict columnar purity vs pragmatic materialization

Martin/Hickey favor strict P1 compliance: every `.to_pylist()` and dict-of-lists accumulation is a violation regardless of data volume. Beck/Feathers counter that fixing low-volume paths (UCDP at ~2.3M rows, ACLED at ~800K) adds complexity without preventing any real failure — the 8 GB constraint only binds on GHS-POP (~60M cells). **Resolution: fix GHS-POP and compilation paths (where it matters), defer UCDP/ACLED (where data volume is 60x smaller). Re-evaluate when any non-GHS-POP path exceeds 5M rows.**

**Source:** ADR-031 compliance review (2026-05-21). Cross-ref: C-144, C-145, C-179.

### D-24: Hardware upgrade vs software optimization for 8 GB ceiling

Nygard/Kleppmann argue the 8 GB server is the wrong constraint to optimize for — a €5/month upgrade to 16 GB CPX42 would eliminate all current OOM risks with zero code changes. Martin/Hickey counter that the code should be correct regardless of hardware: `data.copy()` on a 14 GiB array and `.read_bytes()` on output files are bugs in any memory budget. **Resolution: both — fix the bugs (they make the code simpler, not more complex), and document swap as a safety net. Hardware upgrade is an operational decision, not a code decision.**

**Source:** ADR-031 compliance review (2026-05-21). Cross-ref: C-173 (no swap), C-177 (_aggregate_to_prio_grid copy).

### ~~D-25~~: Dead function retention — `_aggregate_to_prio_grid` after v1.2.18

Feathers argues retaining `_aggregate_to_prio_grid` (no longer called from the builder) creates a maintenance hazard: tests exercise a dead path, and a future developer might re-activate it without noticing the P3 violation. Beck argues the function is tested, documented with a warning, and deletion would break 7 passing tests — the risk of re-activation is lower than the risk of deleting tested code. **Resolution: retain with docstring warning, track as C-177. Delete only when the test suite is restructured to test alignment via `_aggregate_with_alignment` instead.**

**Resolved 2026-05-24:** Retain with docstring warning (current state). Re-evaluate at next refactor cycle when `_aggregate_with_alignment` tests fully replace the old function's test coverage. Tier recalibrated to 4 (C-177).

**Source:** ADR-031 compliance review (2026-05-21). Cross-ref: C-177.

### D-26: Discovery probing cost vs cache staleness (UCDP candidate/dot9)

Nygard argues the 98+ discovery probes per run are a reliability risk: if UCDP starts rate-limiting, the pipeline fails before any useful work. A discovery cache (persist known versions, probe only the frontier) reduces API calls from 98+ to 1-3. Kleppmann counters that a discovery cache introduces a staleness window: if UCDP retracts a version or changes the available set, the cache would serve stale metadata. Beck notes the current approach "works fine" and the optimization should wait for evidence of rate-limiting. **No resolution yet — monitor for rate-limiting before investing in a discovery cache.**

**Source:** Expert code review of harvest caching (2026-05-21). Cross-ref: C-181 (discovery probing).

### D-27: Two-tier cache (UCDP) vs single-tier cache (ACLED/GHS-POP)

Martin argues all harvesters should use two-tier caching (file exists + digest match + post-fetch digest comparison for change detection), creating a uniform contract enforced by a shared base. Hickey argues the distinction is correct: mutable sources (UCDP candidate, updated monthly) need change detection; immutable sources (GHS-POP epochs, ACLED historical years) don't — re-downloading 450 MB to confirm it hasn't changed is waste. The ADR should document both tiers as valid choices, with selection criteria based on source mutability. **Resolution: document in harvest idempotence ADR. Two-tier for mutable sources, single-tier for immutable sources, with source-declared mutability.**

**Source:** Expert code review of harvest caching (2026-05-21). Cross-ref: C-184, C-185, C-44.

### ~~D-28~~: One function vs two for digest lookup (`last_digest` + `last_digest_for_version`)

Ousterhout and Hickey argue for merging into a single function with optional `version` parameter — eliminates the desynchronization bug class (C-182 was fixed in one function, missed in the other until falsification F5). GoF recommends a shared `_find_latest_valid_entry` helper with both public functions as thin wrappers — preserves the API while centralizing logic. Martin values the explicit naming. Feathers cautions that changing 15+ call sites is a refactor that should be done separately from a bug fix. Beck: "make it work first, then make it right."

**Resolved 2026-05-24:** Keep two functions (current state). C-182 bug fixed in both. The shared `_find_latest_valid_entry` helper (GoF recommendation) is a nice-to-have for the next provenance refactor, not a risk.

**Source:** Expert code review of provenance/shapefile (2026-05-21). Cross-ref: C-187 (digest-field assumption), C-182 (original desync bug).

### D-29: Shapefile harvester retrofit depth — full outcome compliance vs organic

Nygard and Martin argue for full outcome-vocabulary compliance now (add try/except, record `"failed"` entries, use `"outcome": "success"/"unchanged"`). Feathers and Beck argue the current code works correctly via backward compat and the retrofit should happen organically when the shapefile harvester is next touched or when V-Dem is added. Hickey notes `"changed": True/False` is accidental complexity but not dangerous. **Trigger: when shapefile harvester is next touched for a bug fix, or when V-Dem requires shapefile-like ingestion (trigger rewritten during review-rr 2026-05-24). No resolution yet — the shapefile harvester is rarely touched (one-time artifact).**

**Source:** Expert code review of provenance/shapefile (2026-05-21). Cross-ref: C-186 (shapefile lacks outcome vocabulary), C-44 (harvest pipeline template).

### ~~C-193~~: Deployment guide GHS-BUILT-S download size overstated (~5 GB vs ~2.1 GB)

| Field | Value |
|-------|-------|
| ID | C-193 |
| Tier | 4 |
| Source | Falsification audit round 2 — merge-readiness (2026-05-23) |
| Trigger | Resolved 2026-05-23 |
| Location | `docs/guides/hetzner_deployment_guide.md:173` |

**Resolved 2026-05-23.** Fix: Changed "~5 GB" to "~2 GB" and "~6 minutes" to "~3 minutes" in the GHS-BUILT-S deployment guide paragraph. Original values were copied from the GHS-POP paragraph without adjustment for GHS-BUILT-S's smaller rasters (~178 MB vs ~350 MB per epoch, 12 × 178 MB ≈ 2.1 GB).

Cross-ref: C-192 (resolved — recurring operational integration gap).

### ~~C-194~~: Raster harvesters (GHS-POP, GHS-BUILT-S) lack `logger.error` before bare `raise` — ADR-008

| Field | Value |
|-------|-------|
| ID | C-194 |
| Tier | 4 |
| Source | Falsification audit round 2 — merge-readiness (2026-05-23) |
| Trigger | Resolved 2026-05-23 |
| Location | `src/datafactory_harvester/sources/ghsbuilts.py:185,205`, `src/datafactory_harvester/sources/ghspop.py:181,201` |

**Resolved 2026-05-23.** Fix: Added `logger.error("Download failed for epoch %d: %s", epoch, url)` before bare `raise` in `except RequestException` blocks, and `logger.error("Bad ZIP file for epoch %d: %s", epoch, url)` before bare `raise` in `except BadZipFile` blocks — in both `ghsbuilts.py` and `ghspop.py`. The `__post_init__` validation raises are left as-is (config validation in frozen dataclass constructors — no operational context to log).

Cross-ref: C-186 (shapefile harvester lacks outcome vocabulary).

### C-195: 37 falsification test files accumulated without curation (3,129 lines) — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-195 |
| Tier | 4 |
| Source | repo-assimilation v1.2.20 (2026-05-24) |
| Trigger | 5th data source adds another 5-8 falsification files, pushing total past 40 files — test suite becomes hard to navigate and maintains stubs for long-resolved concerns |
| Location | `tests/test_falsification_*.py` (37 files, 3,129 lines, 129 test functions) |

Falsification audits produce `test_falsification_*.py` files containing failing test stubs that flip green after fixes. Over 10+ audit rounds (GHS-POP memory, coverage parity, visual audit, merge-readiness ×2, deployment ×2, plus earlier UCDP/ACLED audits), 37 files have accumulated. Many test stubs target concerns that are now resolved (C-190, C-191, C-193, C-194) — their stubs pass but serve no ongoing purpose beyond documentation that the fix exists. The test files are not consolidated by concern or source: `test_falsification_ghsbuilts_coverage_parity.py`, `test_falsification_ghsbuilts_merge_ready.py`, `test_falsification_ghsbuilts_deploy_v2.py` all test overlapping aspects of GHS-BUILT-S readiness. Curation options: (a) archive resolved stubs into a `tests/archive/` directory, (b) consolidate per-source stubs into one file per source, (c) tag resolved stubs with `@pytest.mark.resolved` and skip in CI. Tier 4 because: (a) all tests pass, (b) no correctness impact, (c) single-developer scope, (d) the accumulation is a navigation and maintenance burden, not a risk.

Cross-ref: C-189 (GHS-BUILT-S coverage parity gap), C-180 (no falsification for non-GHS-POP paths), C-164 (WET-before-DRY broader inventory).

### ~~C-196~~: 7 of 8 ARCHITECTURE.md files have stale module lists (18 files undocumented) — RESOLVED

Resolved 2026-05-25. Updated 5 ARCHITECTURE.md files (viewpoint, consolidation, compilation, harvester + intent contracts section). Removed stale synthetic reference from compilation ARCHITECTURE.md. All 14 falsification test stubs pass. Moved to resolved archive.

### ~~C-197~~: docs/CICs/README.md lists 21 active contracts but 28 exist (7 missing) — RESOLVED

Resolved 2026-05-25. Added 7 missing CIC entries to docs/CICs/README.md: GhsPopConfig, GhsBuiltSConfig, GhsPopViewpointConfig, GhsBuiltSViewpointConfig, AssemblyConfig, PregriddedCompilationConfig, SourceEntry. Index now lists all 28 active contracts. Moved to resolved archive.

### ~~C-198~~: docs/sources/README.md references 4 catalog cards that don't exist — RESOLVED

Resolved 2026-05-25. Created 4 missing catalog cards: ucdp.md, acled.md, priogrid_static.md, gaul_admin.md. All follow the ADR-033 schema established by ghspop.md and ghsbuilts.md. Moved to resolved archive.

### ~~C-199~~: ADR-026 ACLED credential env vars contradict code — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-199 |
| Tier | 3 |
| Source | review-base-docs (2026-05-25) |
| Trigger | New contributor reads ADR-026 lines 18/66 and sets `ACLED_ACCESS_KEY`/`ACLED_EMAIL` instead of actual `ACLED_USERNAME`/`ACLED_PASSWORD` |
| Location | `docs/ADRs/026_credential_management.md` lines 18, 66, 99 |

ADR-026 contains contradictory ACLED credential env var names. Lines 18 and 66 say `ACLED_ACCESS_KEY`/`ACLED_EMAIL` (early design). Line 99 says `ACLED_USERNAME`/`ACLED_PASSWORD` (actual). Code uses `ACLED_USERNAME`/`ACLED_PASSWORD`. Fail-loud catches the wrong vars (missing env var error), but a contributor wastes time debugging.

Resolved 2026-05-25. Corrected all `ACLED_ACCESS_KEY`/`ACLED_EMAIL` → `ACLED_USERNAME`/`ACLED_PASSWORD` in ADR-026.

### ~~C-200~~: Grid dimension order wrong in ADR-005 and CLAUDE.md — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-200 |
| Tier | 3 |
| Source | review-base-docs (2026-05-25) |
| Trigger | Developer reads ADR-005 or CLAUDE.md and writes code assuming 3D `(n_cells, n_steps, n_features)` shape instead of actual 4D `[T, H, W, C]` |
| Location | `docs/ADRs/005_testing_as_mandatory_critical_infrastructure.md` line 101, `CLAUDE.md` line 44 |

ADR-005 line 101 claims compiled grid shape is `(n_cells, n_steps, n_features)` (3D). CLAUDE.md line 44 claims `(cells, time, features)`. Actual shape is `[T, H, W, C]` = `(time, height=360, width=720, channels)` (4D), correctly documented in ADR-024. Code at `grid_compilation.py` confirms 4D. A developer following ADR-005 or CLAUDE.md would index arrays wrong.

Cross-ref: ADR-024 (correct), C-128 (resolved — related grid shape issue in scripts).

Resolved 2026-05-25. Updated ADR-005 and CLAUDE.md to match ADR-024's `[T, H, W, C]`.

### ~~C-201~~: 4 CICs with contract drift post-v1.2.21 — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-201 |
| Tier | 4 |
| Source | review-base-docs (2026-05-25) |
| Trigger | Developer reads CIC and writes code based on wrong contract (swapped args, missing field, wrong shapes) |
| Location | `docs/CICs/AssemblyConfig.md`, `docs/CICs/SpatioTemporalGrid.md`, `docs/CICs/ComparisonResult.md`, `docs/CICs/GhsPopViewpointConfig.md` |

Four CICs have contract drift: (1) AssemblyConfig missing `ghsbuilts_grid_dir` field added in GHS-BUILT-S sprint; (2) SpatioTemporalGrid documents arrays as 2-D `[H, W]` but they're 1-D, and temporal defaults show 432 months instead of 456; (3) ComparisonResult example has `compare_snapshots` arguments swapped (code: `old_path, new_events`, CIC: `new_events, prev_path`); (4) GhsPopViewpointConfig section 6 missing `ValueError` on invalid `temporal_interpolation`.

Resolved 2026-05-25. Updated all 4 CICs to match current code.

### ~~C-202~~: Operational docs stale — logging standard, deployment guide, hardened protocol, ADR counts — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-202 |
| Tier | 4 |
| Source | review-base-docs (2026-05-25) |
| Trigger | 7th data source integration — every new source increases the count drift across docs |
| Location | `docs/standards/logging_and_observability_standard.md`, `docs/guides/hetzner_deployment_guide.md`, `docs/contributor_protocols/hardened_protocol_template.md`, ADRs 009/010/011/012/018/020/021/022/033/034, `docs/ADRs/README.md` |

Pattern of cumulative documentation staleness: (1) logging standard has 3 wrong ledger paths, 8 missing ledgers, 1 vestigial synthetic entry; (2) deployment guide says 51 features (actual 53) and ~820 tests (actual ~1157); (3) hardened protocol has vestigial synthetic generation references; (4) 5 ADRs reference `reports/technical_risk_register_resolved.md` (moved to `reports/archive/`); (5) ADR-011 says "0/9" (should be "0/11"); (6) ADR-021 says "51 features" (should be 53); (7) ADR-022 diagram says "(9 steps)"; (8) ADR-033 says "5 data sources" (should be 6); (9) ADR-012 uses synthetic as path example; (10) ADR-018 SLO table missing GHS-POP/GHS-BUILT-S; (11) ADR-009 wrong file path; (12) ADR-034 minor math; (13) ADR README missing 7 entries.

Cross-ref: C-196, C-197, C-198 (same documentation drift pattern, resolved earlier same day).

Resolved 2026-05-25. Updated all 13 locations in a single commit.

---

## Deferred by Design

### C-10: Ontology vocabulary overhead
Terms like "Source Nodes," "Compilation Edges," "Explicit Non-Entities" are precise but add conceptual overhead. For a 7-package project, governance is heavy. **Accepted: governance has proven itself (ADR-008 caught bugs in 3 audits). Cost is documentation maintenance, not development velocity.**
**Source:** Ousterhout

### C-38: Version string year offset assumes 21st century
`_DOT9_YEAR_OFFSET = 2000` / `_CANDIDATE_YEAR_OFFSET = 2000` in `ucdp_dot9.py:50` and `ucdp_candidate.py:43`. Breaks silently for pre-2000 or post-2099 data. UCDP data starts 1989 (annual uses full version strings). **Trigger: never (2099 is 73 years away).**
**Source:** Repo assimilation

### C-41: Digest truncation collision risk
`DIGEST_TRUNCATE = 16` hex chars = 64-bit space. 50% collision at ~4B items. Fine at ~2M events. **Trigger: consider when total records exceed 100M or digests are used as unique keys.**
**Source:** Repo assimilation

### C-06: Provenance logic should be a composable utility
Every module independently calls `append_ledger_entry()` with its own format. A `@provenance` decorator or context manager would centralize ~50 lines of boilerplate across 4 modules. Kleppmann (Ch.12 pp.499-501) advocates Unix philosophy: composable tools with uniform interfaces. Our current approach (each module calls the same function with its own format) is composition via shared function, not shared abstraction — acceptable at this scale. **Accepted: explicit > implicit for now.**
**Source:** Hickey. DDIA Ch.12 pp.499-501.

### C-07: Frozen dataclass pattern repeated
7 config classes follow the same frozen-dataclass-with-`__post_init__` pattern. No shared Protocol or base. A declarative validation approach or `ValidatedConfig` Protocol would reduce duplication. Kleppmann (Ch.4 p.127) argues schemas serve as documentation that "cannot diverge from reality" — our frozen dataclasses with `__post_init__` validation are effectively runtime schemas. **Accepted: explicit repetition is simple and readable; each config is its own schema.**
**Source:** Hickey. DDIA Ch.4 p.127.

### C-32: Source registry returns `Any`
`fetch_source` returns `Any` (widened from `Path` for candidate's `list[dict]`). Sources, consolidators, and builders are intentionally heterogeneous — each has a different signature. The three strategy registries (aggregation, survivorship, temporal_distribution) already use precise types. Kleppmann (Ch.4 p.126) notes dynamically generated schemas are an acceptable trade-off when sources have heterogeneous structures. **Accepted: heterogeneous signatures are by design.**
**Source:** GoF, Hickey (expert review 5). DDIA Ch.4 p.126. Reclassified 2026-04-06.
