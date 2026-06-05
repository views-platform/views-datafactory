# Technical Risk Register

**Date:** 2026-03-17 (updated 2026-06-05)
**Source:** Multi-expert engineering review, repo assimilation, falsification audits, expert code review (Martin, GoF, Feathers, Nygard, Kleppmann, Ousterhout, Hickey, Beck), magic-values compliance audit, stale-zarr incident 2026-04-24, pipeline verification audit 2026-04-30, ACLED integration test review 2026-05-02, ACLED test review 2026-05-03, ACLED compilation test review 2026-05-05, base documentation review 2026-05-07, ACLED harvester test review 2026-05-07, GHS-POP harvester test review 2026-05-18, GHS-POP viewpoint test review 2026-05-19, PR #53 review 2026-05-20, GHS-POP memory falsification + expert code review 2026-05-20, repo-assimilation 2026-05-20, ADR-031 compliance review 2026-05-21, harvest caching expert code review 2026-05-21, PR #59 falsification audit round 2 2026-05-21, provenance/shapefile expert code review 2026-05-21, GHS-BUILT-S review-rr triage 2026-05-22, GHS-BUILT-S coverage parity falsification 2026-05-22, GHS-BUILT-S visual audit falsification 2026-05-22, GHS-BUILT-S visual audit run 2026-05-22, C-190 resolution 2026-05-23, GHS-BUILT-S merge-readiness falsification 2026-05-23, pre-merge sprint (C-191/C-192/C-168/C-174) 2026-05-23, GHS-BUILT-S merge-readiness falsification round 2 2026-05-23, repo-assimilation v1.2.20 2026-05-24, tech-debt-cleanup investigation 2026-05-24, review-rr strategic + prioritize 2026-05-24, review-base-docs 2026-05-25, V-Dem test coverage parity falsification 2026-05-26, V-Dem ADR/guide compliance falsification 2026-05-26, V-Dem SOLID/package/file-org falsification 2026-05-26, review-rr strategic curation 2026-05-26, review-base-docs 2026-05-26, V-Dem visual audit falsification 2026-05-26, V-Dem visual audit documentation falsification 2026-05-26, sprint S4 standalone fixes (C-175/C-129/C-149) 2026-05-27, merge-readiness falsification (C-222) 2026-05-27, review-rr strategic curation 2026-05-28, SHDI review-diff 2026-05-29, expert code review C-164 2026-05-30, digest verification expert code review + 3 falsification audits 2026-06-02, preflight netrc falsification 2026-06-02, status page understanding falsification 2026-06-04, status page fix plan falsification 2026-06-04, ADR-040 scoping 2026-06-05, test-review area-majority effort 2026-06-05, review-base-docs area-majority effort 2026-06-05
**Status:** 244 concern IDs assigned (C-28 merged into C-31, C-107 merged into C-60, C-183 merged into C-44, C-44 merged into C-164, C-03 merged into C-176): 184 resolved, 57 open concerns (4 Tier 2, 11 Tier 3, 36 Tier 4, 6 deferred by design; 1 with fired trigger), 6 open disagreements. 161 resolved concerns as full entries + 19 early-archive reference rows + 4 demoted in active register + 27 resolved disagreements in archive. 33 disagreement IDs total: 27 resolved, 6 open.
**Archive:** Resolved concerns and disagreements are in `archive/technical_risk_register_resolved.md`.

**Ranking criteria:** Impact if wrong x likelihood x detectability. Items marked **[DEFER]** are accepted risks or wait for a specific trigger condition. See ADR-020 for governance rationale.

---

## Open Items Summary

| ID | Tier | Title | Trigger | Package |
|----|------|-------|---------|---------|
| C-88 | 2 | SSH not restricted to PRIO/Uppsala IPs | Before granting additional SSH users | Server hardening |
| C-121 | 4 | Phase 6.4 documented but unexecuted (lessons from C-87) | Before executing Phase 6.4 | Server hardening |
| C-36 | 4 | UCDP API contract has no schema versioning | UCDP announces API v2 | UCDP schema |
| C-37 | 4 | `date_prec=5` semantics hardcoded | UCDP publishes codebook | UCDP schema |
| C-45 | 4 | No Parquet schema evolution strategy | UCDP removes/renames a field | UCDP schema |
| C-46 | 4 | No ledger write idempotency | External systems consume ledger | — |
| C-32 | — | Source registry returns `Any` | Accepted by design | — |
| C-29 | 4 | No end-to-end integration test — trigger fired, accepted at v1.0 | Full-scale e2e with all 9+ sources, or 2nd deployment target | Test infra |
| C-70 | 4 | No circuit breaker for UCDP API | Multi-operator deployment | UCDP resilience |
| C-72 | 4 | HTTP 429 not distinguished from 500 | UCDP returns 429s | UCDP resilience |
| C-74 | 4 | CompilationConfig leaks strategy vocabulary | New developer needs IDE discoverability | — |
| C-78 | 4 | `_place_events` hard to test in isolation | Compilation tests exceed 5s | Test infra |
| C-79 | 4 | Compilation/consolidation require real Parquet I/O | Test suite exceeds 30s | Test infra |
| C-97 | 4 | Basic auth + Caddy scalability ceiling at ~30-50 users | Before consumer count exceeds 30 | — |
| ~~C-109~~ | ~~4~~ | ~~Advisory file locks (fcntl) don't work across NFS~~ | Demoted to tech-debt backlog 2026-05-28 | — |
| ~~C-115~~ | ~~4~~ | ~~Summary detection threshold (>= vs >) is architectural~~ | Demoted to tech-debt backlog 2026-05-28 | — |
| C-116 | 4 | No retry on remote zarr network failures | Consumer reports transient failures | Query resilience |
| C-117 | 4 | Remote zarr downloads all spatial cells before region filter | Consumer queries single country over slow connection | Query performance |
| C-131 | 2 | No external monitoring for cron job failure on Hetzner | Server reboots without cron re-enable or user deletion | Operational monitoring |
| ~~C-135~~ | ~~4~~ | ~~No runtime type validation for zarr `.zattrs` values~~ | Demoted to tech-debt backlog 2026-05-28 | — |
| C-136 | 4 | `read_last_entries()` crashes on non-UTF8 ledger files | Disk corruption or binary append to JSONL ledger | Operational monitoring |
| C-126 | 3 | No transform layer — 14 viewser transforms not replaceable | Model migration requires derived features | Migration scope |
| C-177 | 4 | `_aggregate_to_prio_grid` holds source + copy simultaneously (ADR-031 P3) | Function is re-activated for a new data source | ADR-031 compliance |
| C-179 | 4 | Consolidation dedup uses `.to_pylist()` + Python set (ADR-031 P1) | Consolidated store exceeds ~5M rows on 8 GB machine | ADR-031 compliance |
| C-180 | 4 | No falsification tests for non-GHS-POP compilation/viewpoint paths | Memory regression introduced in UCDP or ACLED path | Test coverage |
| C-181 | 4 | UCDP candidate/dot9 discovery probes API even when all versions cached | UCDP rate-limits or blocks IP after repeated full-range probes | Harvest efficiency |
| ~~C-184~~ | ~~3~~ | ~~ACLED `_year_is_cached` checks file existence, not file integrity~~ | Resolved 2026-06-02 (PR #98: `_recompute_content_digest` verifies content) | Harvest correctness |
| C-185 | 4 | GHS-POP caching has no digest comparison (no change detection) | JRC silently updates a GeoTIFF epoch without changing the URL | Harvest correctness |
| C-186 | 3 | Shapefile harvester lacks outcome vocabulary; ADR-032 overstates compliance | New harvester trusts ADR-032 claim that all harvesters record failed entries | Harvest correctness |
| C-189 | 4 | GHS-BUILT-S test coverage parity gap — 19% of combined other sources | Production incident on GHS-BUILT-S path that existing GHS-POP/ACLED tests would have caught | Test coverage |
| C-223 | 3 | Compilation pipeline allocates full grid in RAM (bounded-memory R&D) | Next data source (WDI: 20-50 features) pushes single-source compile past 16 GB | Scaling headroom |
| C-224 | 4 | No server backup or disaster recovery plan | Disk failure or accidental data deletion on Hetzner server | Server hardening |
| D-23 | — | ADR-031 P1 strict columnar purity vs pragmatic materialization | Open | ADR-031 compliance |
| D-26 | — | Discovery probing cost vs cache staleness (UCDP candidate/dot9) | Open | Harvest caching |
| D-29 | — | Shapefile harvester retrofit depth — full outcome compliance vs organic | Open | Harvest correctness |
| D-30 | — | Config validator extraction depth — utility functions vs declarative specs | Open | WET-before-DRY |
| D-31 | — | Harvest script consolidation — single unified script vs thin delegates | Open | WET-before-DRY |
| C-230 | 4 | Script layer (harvest + pipeline) has zero unit tests | Pattern #7/#8 extraction changes behavior with no test to catch regression | Test coverage |
| C-231 | 4 | No compilation idempotence guard — silent recompilation with stale inputs | Operator re-runs compilation after viewpoint re-built with different parameters | Compilation correctness |
| ~~C-235~~ | 3 | ~~Source registry declares nonexistent SHDI downstream entries~~ | Resolved: #105 removed SHDI features and phantom entries | Source registry |
| C-236 | 4 | Status page artifact mapping requires manual update per source | Next source integration omits status page mapping | Status page |
| C-237 | 3 | Status page generation + delivery verification gap | Pipeline fails at step 12+; or EXIT trap runs but output not at Caddy path | Operational monitoring |
| C-238 | 3 | Issue #104 stale Caddy claims + orphaned daily cron requirement | Developer picks up #104 and follows wrong Caddy instructions | Operational monitoring |
| C-239 | 2 | Issue #104 paths produce silent wrong status page | Developer sets up daily cron using #104's --data-dir/--provenance-dir commands | Operational monitoring |
| C-240 | 4 | generate_status.py docstring specifies nonexistent /www/ path | Developer follows script's usage example verbatim | Status page |
| C-241 | 4 | No invariant for intensive feature conservation across resolution or aggregation | First consumer aggregates intensive features (HDI, built-up fraction) to country-month or grid resolution changes | Aggregation correctness |
| C-242 | 2 | ADR-040 count conservation invariants accepted but zero test enforcement | Code change modifies skip/exclusion logic in compilation or CM aggregation | Count conservation |
| C-243 | 3 | ADR-040 hierarchical reconciliation untested (gaul0/1/2 sum equality) | Area-majority join (#118) changes gaul assignment method, or new admin system added | Count conservation |
| C-244 | 4 | 4 CICs + ADR-025 not updated after ADR-040 acceptance | Investigation branch merges without updating CICs/ADRs to reference ADR-040 | Count conservation |
| ~~D-32~~ | — | ~~`assembled` flag vs removing features from partially-integrated sources~~ | Resolved: chose removal (#105) | Source registry |
| D-33 | — | Pipeline-path information: registry field vs standalone mapping vs convention | Open | Source registry |
| C-144 | 3 | Compilation `to_pydict()` materializes millions of Python objects | Consolidation store exceeds ~5M events | Compilation memory |
| C-145 | 3 | Viewpoint builder loads full consolidated store into memory | Consolidated store exceeds ~5M rows on constrained hardware | Viewpoint memory |
| C-146 | 4 | Assembly logic lives in script, not importable package | Assembly orchestration refactored or new assembly path added | Testability |
| C-147 | 4 | No pipeline orchestrator in repository | Operator runs scripts out of order or skips a step | Operations |
| C-148 | 4 | Hardcoded Hetzner server IP in `defaults.py` | Server migrates to new IP or hostname | Configuration |
| C-153 | 3 | ACLED API has no TotalCount — silent truncation undetectable | ACLED enforces server-side result caps within a page | ACLED data integrity |
| C-154 | 4 | ACLED_FEATURES config duplicated between script and tests | Feature filter values changed in script but not tests | ACLED test quality |
| C-155 | 4 | No shared visual audit framework — per-source scripts are idiosyncratic | Before 6th pipeline source (WDI) requires a verify script | Visual audit |
| C-195 | 4 | 37 falsification test files accumulated without curation (3,129 lines) | Next audit round adds files, or total exceeds 45 | Test hygiene |
| C-173 | 4 | Hetzner server memory headroom (CPX42 + swap) | Software optimization needed before next large source | Server hardening |
| C-164 | 3 | Cross-layer WET debt: 6 sources replicate patterns across all 4 layers — **trigger fired** | Before WDI integration or next data source | WET-before-DRY |
| ~~C-225~~ | ~~4~~ | ~~SHDI version drift in docs~~ | Resolved 2026-05-29 (version strings corrected) | SHDI docs |
| ~~C-226~~ | ~~4~~ | ~~SHDI shapefile download failure writes no ledger entry~~ | Resolved 2026-05-29 (try/except + ledger entry added) | SHDI harvest |
| ~~C-227~~ | ~~2~~ | ~~SHDI inner join can silently drop rows~~ | Resolved 2026-05-29 (fail-loud row-count guard + test) | SHDI harvest |
| ~~C-228~~ | ~~4~~ | ~~Dead `download_url` property~~ | Resolved 2026-05-29 (property + dead test removed) | SHDI harvest |
| ~~C-229~~ | ~~4~~ | ~~Doc claims "1 request per run"~~ | Resolved 2026-05-29 (updated to "5 requests per run") | SHDI docs |
| C-156 | 3 | ACLED temporal range mismatch — zero-fill before 2020 in assembled grid | Model uses ACLED features for pre-2020 months without awareness of zero-fill | ACLED assembly |
| C-159 | 4 | ACLED snapshot archiving and revision comparison paths untested | Archiving logic implicated in data integrity incident | ACLED test coverage |
| ~~C-160~~ | ~~4~~ | ~~ACLED `fetch_paginated` string-data corruption has no guard~~ | Demoted to tech-debt backlog 2026-05-28 | — |
| C-10 | — | Ontology vocabulary overhead | Accepted | — |
| C-38 | — | Version string year offset assumes 21st century | Never (2099) | — |
| C-41 | — | Digest truncation collision risk | Records exceed 100M | — |
| C-06 | — | Provenance composability | Deferred by design | — |
| C-07 | — | Frozen dataclass pattern repeated | Deferred by design | — |

## Work Packages

Items that should be resolved together:

| Package | Items | Trigger |
|---------|-------|---------|
| **Server hardening** | C-88, C-121, C-173, C-224 (C-84, C-85, C-86, C-87 resolved; C-173 recalibrated 3→4) | Before production deployment |
| **UCDP API resilience** | C-70, C-72 | Multi-operator deployment |
| **UCDP schema defense** | C-36, C-37, C-45, ~~C-175~~ | UCDP API change (C-175 resolved 2026-05-27) |
| **Test infrastructure** | C-29, C-78, C-79, C-146 (C-60, C-169 resolved; C-146 recalibrated 3→4) | Test suite growth |
| **Operational monitoring** | C-131, ~~C-132~~, C-136, C-147, ~~C-191~~, C-237, C-238, C-239 | Before relying on Hetzner pipeline without manual checks (C-191, C-132 resolved) |
| **Source registry integrity** | ~~C-235~~, C-236, ~~D-32~~, D-33 | Before next data source integration (WDI) (C-235, D-32 resolved #105) |
| **Scaling headroom** | C-144, C-145, C-223 | Before consolidated store exceeds ~5M rows or next data source pushes compile past 16 GB |
| ~~**Data integrity**~~ | ~~C-138~~, ~~C-149~~ (C-137, C-139 resolved 2026-05-26, C-149 resolved 2026-05-27, C-138 resolved 2026-05-28) | Resolved 2026-05-28: all items resolved |
| ~~**Data boundary**~~ | ~~C-130~~, ~~C-133~~, ~~C-134~~, C-135 | Resolved 2026-05-28: C-130 resolved, C-135 demoted (C-133, C-134 resolved earlier) |
| **Harvest correctness** | ~~C-182~~, ~~C-184~~, C-185, C-186, ~~C-188~~ | Before relying on harvest caching for correctness |
| **Count conservation** | C-241, C-242, C-243, C-244 | Before area-majority join (#118) merges or next data source adds count features |
| **WET-before-DRY refactor** | ~~C-44~~, C-07, C-155, C-164, C-195, C-230 | Before WDI or next refactor sprint (V-Dem added without extraction; C-44 merged into C-164; C-230 blocks safe extraction of patterns #7/#8) |
| ~~**V-Dem test & doc gaps**~~ | ~~C-203~~, ~~C-204~~, ~~C-205~~, ~~C-206~~, ~~C-207~~, ~~C-208~~, ~~C-209~~, ~~C-210~~, ~~C-211~~, ~~C-212~~, ~~C-213~~, ~~C-214~~, ~~C-215~~, ~~C-216~~ | Resolved 2026-05-26: all items resolved in V-Dem sprint |
| **Migration scope** | ~~C-125~~, C-126 | Before claiming full viewser replacement for the fleet |

---

## Tier 1 — Fix Immediately

---

## Tier 2 — Fix Before Sharing Server Access

### C-88: SSH not restricted to PRIO/Uppsala IPs — [DEFER]
SSH is open to all source IPs. IT head advised whitelisting PRIO and Uppsala VPN IPs via fail2ban or Hetzner firewall, requiring VPN for SSH access. **Trigger: before granting additional SSH users, or when PRIO IT provides VPN CIDR ranges for firewall rules (trigger rewritten during review-rr 2026-05-24).** Procedure documented in `hetzner_deployment_guide.md` Phase 6.4. Requires PRIO/Uppsala VPN CIDR ranges from IT.
**Source:** PRIO IT security guidance, server setup 2026-03-28


### C-131: No external monitoring for cron job failure on Hetzner — [RESOLVING]
The monthly pipeline runs via a single cron job (`0 0 21 * *`) under the `views-deploy` user. If the cron daemon crashes, the server reboots without re-enabling cron, or the `views-deploy` user is deleted during maintenance, the pipeline silently stops running. No external monitoring (cronitor, uptime check, systemd watchdog) exists to detect this. ADR-018 explicitly defers monitoring to operators (line 76: "Operators must monitor and intervene during outages") but no operator-side monitoring has been configured. The `ALERT_EMAIL` variable in `refresh_pipeline.sh:68` is a documented TODO (deployment log line 332) and is not set on the server.

**Fix applied (2026-04-22):** Added optional heartbeat ping to `refresh_pipeline.sh` — on successful pipeline completion, pings `$HEARTBEAT_URL` (env var) if set. Operator must configure a healthchecks.io/cronitor service and set the URL on the server. Architectural review confirmed this is a deployment concern (not a new module) per ADR-018.

**Trigger:** Hetzner server reboots and cron daemon fails to restart, or `views-deploy` user is removed during server maintenance.
**Location:** Server crontab (`views-deploy` user), `scripts/refresh_pipeline.sh:61-72` (failure trap), `docs/ADRs/018_operational_resilience.md:76,90`.
**Source:** Falsification audit P1/P2 (2026-04-22).


### C-239: Issue #104 paths produce silent wrong status page

| Field | Value |
|-------|-------|
| ID | C-239 |
| Tier | 2 |
| Source | falsification audit (2026-06-04, G4) |
| Trigger | Developer sets up the daily status page cron using #104's commands verbatim: `--data-dir /srv/views-data --provenance-dir /srv/views-data/provenance` |
| Location | GitHub issue #104 (body text — both the refresh_pipeline.sh step and the cron entry), `scripts/generate_status.py:9` (docstring usage example) |

Issue #104 specifies `--data-dir /srv/views-data` and `--provenance-dir /srv/views-data/provenance` for both the pipeline step and the daily cron entry. On the server, `/srv/views-data/` contains only three per-file symlinks (`grid.zarr`, `dataframe.parquet`, `status.html`) — no `raw/`, `compiled/`, `assembled/` subdirectories. `/srv/views-data/provenance/` does not exist (no symlink, no directory). `generate_status.py`'s `check_stage()` function looks for data artifacts at `data_dir / artifact.data_glob` and provenance ledgers at `provenance_dir / artifact.ledger` — both resolve to nonexistent paths under `/srv/views-data/`.

**Impact:** Following #104's commands produces a status page where every source and stage shows "missing" — a silent wrong answer. No error is raised. The page renders correctly but with entirely incorrect content. This meets Tier 2 criteria: structural fragility producing silent wrong output under a realistic change scenario (setting up the cron).

**Resolution:** Close or rewrite #104. The correct invocation uses relative paths from the repo root (as the deployment guide line 377 and refresh_pipeline.sh line 95-96 already do): `uv run python scripts/generate_status.py --output data/status.html` (with defaults for `--data-dir` and `--provenance-dir` resolving to `data/` and `provenance/` relative to cwd).

Cross-ref: C-238 (stale Caddy claims in same issue), C-237 (status page generation/delivery), C-240 (docstring path).


### C-242: ADR-040 count conservation invariants accepted but zero test enforcement

| Field | Value |
|-------|-------|
| ID | C-242 |
| Tier | 2 |
| Source | test-review (2026-06-05), area-majority investigation effort |
| Trigger | Code change modifies skip/exclusion logic in `_place_events_columnar` or `grid_to_country_month` without a conservation assertion to catch the regression |
| Location | `src/datafactory_compilation/grid_compilation.py:103-151` (skip variables, no assertion), `src/datafactory_adapters/grid_to_country_month.py:73-99` (exclusion count, no accounting equation), `docs/ADRs/040_count_conservation_and_hierarchical_reconciliation.md` §Validation |

ADR-040 mandates `placed + excluded = input` at every layer boundary (Invariant 1). The variables already exist: `n_skipped_spatial` and `n_skipped_temporal` in `grid_compilation.py:103-151`, and `n_excluded` with `excluded_mask` in `grid_to_country_month.py:73-99`. But these are used only for warning-level logging — no assertion verifies the equation, and no test checks it. The ADR creates a governance expectation that the codebase does not enforce. This is the same structural pattern that allowed C-149: skip counts exist but are informational, not load-bearing.

**Impact:** Tier 2 because a code change that breaks the accounting (adds a new skip reason, changes the exclusion filter, introduces an off-by-one) would silently violate the conservation invariant with no signal. The ADR creates false confidence that counts are conserved.

**Resolution:** (1) Add assertions at both layer boundaries: `assert n_placed + n_skipped_spatial + n_skipped_temporal == table.num_rows` in compilation, and `assert abs(grid_total - (cm_total + excluded_total)) < atol` in CM aggregation. (2) Create `tests/test_count_conservation.py` with synthetic-data tests that verify both equations independently of real data.

Cross-ref: C-241 (intensive feature gap — different invariant), C-243 (hierarchical reconciliation test gap), ADR-040.


## Tier 3 — Improve Quality

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
| Tier | 4 (recalibrated from 3 during strategic curation 2026-05-28) |
| Source | repo-assimilation (2026-04-30) |
| Trigger | When assembly orchestration needs refactoring, or a second assembly path is needed (e.g., different feature sets for different consumers) |
| Location | `scripts/assemble_grid.py` (~350 LOC procedural, not in any `src/datafactory_*` package) |

Every other layer exposes its core logic as an importable function: `consolidate_ucdp()`, `build_ucdp_v1()`, `compile_grid()`, `load_dataset()`. Assembly is the exception — its spatial join, static feature broadcast, and admin boundary merge logic lives entirely in `assemble_grid.py`'s `main()`. `test_assemble.py` tests sub-components (spatial join helper, GID lookup) but cannot import and test the orchestration function directly. Extracting an `assemble_grid()` function into `datafactory_compilation` or a new `datafactory_assembly` package would make the logic importable and directly testable.

**Note (2026-05-24, repo-assimilation v1.2.20):** At 4 sources / 831 lines, the script grows linearly per source (~100-150 lines per source for loading, slicing, and stacking). At source #8-10, `assemble_grid.py` will exceed 1,200 lines of procedural code with no importable interface. The linear growth compounds the testability concern: each new source adds code paths that cannot be unit-tested in isolation.

**Note (2026-05-24, tech-debt-cleanup investigation):** The linear growth mechanism is now identified: lines 240-441 contain 3 source load-validate-align blocks (ACLED 59 lines, GHS-POP 66 lines, GHS-BUILT-S 77 lines = 202 lines total) that are **structurally identical** with only variable-name substitution. Each block: load grid.npy + feature_names.json + time_steps.npy → assert existence → assert_grid_shape → find temporal offset → validate bounds → print diagnostics. A parameterized `_load_source_grid(name, grid_dir, time_steps)` function (~40 lines) would replace all 3 blocks and handle the 5th source without new code. Extraction is safe (no memory or behavioral change — same np.load with mmap_mode="r"), but the function must remain in the script until C-146's testability concern is also addressed (extraction to importable package).

See also C-29 (no end-to-end integration test), C-164 (cross-layer WET debt).

### ~~C-235~~: Source registry declares nonexistent SHDI downstream entries — Resolved #105

| Field | Value |
|-------|-------|
| ID | C-235 |
| Tier | 3 |
| Source | expert-code-review (2026-06-03), pipeline status page initiative |
| Trigger | SHDI viewpoint implemented without removing or updating phantom downstream entries; or new developer reads registry and assumes SHDI is fully integrated |
| Location | `src/datafactory_provenance/source_registry.py:273-278` (SHDI Viewpoint), `src/datafactory_provenance/source_registry.py:315-320` (SHDI Compilation) |

`PIPELINE_SOURCES` contains `SourceEntry` declarations for "SHDI Viewpoint" (with `viewpoint/shdi_v1_ledger.jsonl`) and "SHDI Compilation" (with `compilation/shdi_ledger.jsonl`). No corresponding code exists: no `builders/shdi_v1.py`, no `compile_shdi.py`, no assembly integration. These entries create false expectation of integration completeness. The SHDI harvest entry (line 192-205) declares 4 features (`shdi_shdi`, `shdi_healthindex`, `shdi_edindex`, `shdi_incindex`) that `get_all_features()` returns, causing `verify_remote.py` to expect 79 features when the grid contains 75.

The root cause is that the source registry conflates "this source will eventually produce these features" (planning document) with "these features are in the grid" (deployment document). Six experts in the 8-expert review flagged this as the core issue. See D-32 for the disagreement on the fix approach.

Cross-ref: C-164 (WET debt — SHDI copied patterns), D-32 (assembled flag vs feature removal). GitHub: #101, #103.

### C-237: Status page generation + delivery verification gap

| Field | Value |
|-------|-------|
| ID | C-237 |
| Tier | 3 |
| Source | expert-code-review (2026-06-03), Nygard perspective; falsification audit (2026-06-04, F5) |
| Trigger | Pipeline fails at step 12+ and EXIT trap doesn't fire; or EXIT trap runs successfully but output file doesn't land where Caddy serves it |
| Location | `scripts/refresh_pipeline.sh:47` (`set -euo pipefail`), `scripts/refresh_pipeline.sh:92-98` (EXIT trap), `scripts/generate_status.py:410` (output path default) |

Two gaps in the status page generation chain:

**Gap 1 — Generation reliability:** The original `set -e` concern was mitigated by moving generation into a `trap EXIT` handler (lines 92-98). The EXIT trap fires on normal exit, ERR, SIGTERM, SIGHUP, SIGINT — but NOT on SIGKILL. The `|| echo` pattern inside the trap suppresses `generate_status.py` failures silently.

**Gap 2 — Delivery verification (from falsification audit F5):** Even when the EXIT trap runs and `generate_status.py` succeeds, nothing verifies the output file exists at the path Caddy actually serves (`/srv/views-data/status.html`). The script writes to `data/status.html` (relative to repo). No post-generation check confirms reachability. The v1.2.27 diagnosis was built on HTTP status codes (401/404) without ever verifying whether the file was generated on the server — symptom-based diagnosis, not root-cause verification.

**Mitigation:** #126 proposes adding a verify check to `verify_remote.py` and a file-existence check to the EXIT trap. When implemented, this resolves Gap 2 for deployments but not for the daily cron (see C-238).

Cross-ref: C-131 (no external monitoring for cron), C-238 (orphaned daily cron). GitHub: #101, #104, #123, #126.

### C-238: Issue #104 stale Caddy claims + orphaned daily cron requirement

| Field | Value |
|-------|-------|
| ID | C-238 |
| Tier | 3 |
| Source | falsification audit (2026-06-04, F2+F4); falsification audit round 3 (2026-06-04, H2) |
| Trigger | Developer picks up #104 and follows its instruction that "Caddy configuration changes (none needed)" — leaving the @protected matcher unapplied; or developer works #123 without understanding the manual-steps requirement |
| Location | GitHub issue #104 (body text), GitHub issue #123 (body text), ADR-038 (`docs/ADRs/038_public_status_via_caddy_path_exemption.md`), `docs/guides/hetzner_deployment_guide.md` (section 3.2) |

Three documentation/governance gaps discovered during the status page understanding falsification audit:

**Gap 1 — Stale #104:** Issue #104 (pipeline integration for status page) states "Caddy configuration changes (none needed — Caddy already serves the directory)." This directly contradicts ADR-038 (accepted 2026-06-04) and issue #124, both of which specify a `@protected not path /status.html` matcher is required. #104 is OPEN. A developer working #104 would follow its instructions and skip the Caddyfile change, leaving the status page behind auth.

**Gap 2 — Orphaned daily cron:** The daily cron at 06:00 UTC for status page regeneration is documented in ADR-038 and `hetzner_deployment_guide.md` section 3.2. It is not covered by #123-#126 (the status page fix issues). #125 mentions it in passing ("Also update the daily cron entry (#104)"), deferring to #104 — which has wrong Caddy assumptions. The daily cron is a requirement that fell between old (#104, stale) and new (#123-#126, omitted) issues.

**Gap 3 — #123 doesn't acknowledge manual steps (from falsification audit round 3, H2):** Issue #123 ("What was promised") frames the failure as a technical gap ("supposed to be publicly accessible") but does not state that the status page requires three manual post-pipeline server steps (Caddyfile change, symlink creation, generate_status.py run) that were never communicated clearly. A developer reading #123 would not understand why the page was "supposed" to be live — only that it isn't. This is a hard falsification from round 1 (F3) that persists through round 3.

**Resolution:** (1) Update #104 body to reference ADR-038 and #124 for Caddy changes, or close #104 with a pointer to #123. (2) Ensure daily cron setup is explicitly covered by one of the fix issues. (3) Update #123 to acknowledge that the status page requires manual post-pipeline server steps and that these were not completed during the v1.2.27 deployment.

Cross-ref: C-237 (status page generation + delivery verification), C-131 (external monitoring for pipeline cron). GitHub: #104, #123, #124, #125, #126.

### C-243: ADR-040 hierarchical reconciliation untested (gaul0/1/2 sum equality)

| Field | Value |
|-------|-------|
| ID | C-243 |
| Tier | 3 |
| Source | test-review (2026-06-05), area-majority investigation effort |
| Trigger | Area-majority join (#118) changes the gaul0/1/2 assignment method, or a new admin system is added to the reconciliation family table |
| Location | `tests/test_pipeline_consistency.py` (no reconciliation test), ADR-040 §Validation (hierarchical reconciliation test mandated) |

ADR-040 Invariant 2 requires that within the GAUL reconciliation family, summing count features grouped by gaul0, gaul1, or gaul2 must produce identical totals. No test verifies this. The `gaul1_to_gaul0` mapping is derivable from the assembled grid (each cell has `gaul0_code`, `gaul1_code`, `gaul2_code` channels), but no test checks that grouping by gaul2 then re-grouping by parent gaul1 then re-grouping by parent gaul0 produces the same total as direct gaul0 grouping. If the spatial join assigns a cell to gaul1=X but gaul0=Y where Y does not contain X, the hierarchy is broken silently.

**Resolution:** Add a hierarchical reconciliation test to `tests/test_pipeline_consistency.py` or a new `tests/test_count_conservation.py`: load assembled grid, group by gaul0/1/2, verify sums match within float tolerance.

Cross-ref: C-242 (conservation equation untested), C-241 (intensive feature gap), ADR-040.

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


### C-46: No ledger write idempotency — [DEFER]
`append_ledger_entry()` has no dedup key. Process crash after append but before caller return causes duplicate on retry. Ledger readers tolerate duplicates. Kleppmann (Ch.12 pp.516-518) argues exactly-once semantics require idempotence via operation identifiers — each write carries a unique ID; consumers deduplicate on read. Ch.7 p.231 warns that retrying a successful-but-unacknowledged write without dedup causes silent duplication. Recommended approach: add an `operation_id` field (e.g., content digest of the entry) to each ledger record. **Trigger: consider when ledger is consumed by external systems requiring exactly-once semantics.**
**Source:** Kleppmann (expert review 6). DDIA Ch.7 p.231, Ch.12 pp.516-518.

### C-29: No end-to-end integration test — [DEFER]
Partially addressed by `test_integration.py` (100 events, realistic pipeline). Full-scale end-to-end with all 9 sources untested. **Trigger: full-scale e2e test with all 9+ sources on a clean environment, or 2nd deployment target set up (trigger rewritten during review-rr 2026-05-26).**
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

### C-78: `_place_events` hard to test in isolation — [DEFER]
100 lines of bin-assignment logic tested only indirectly through `compile_grid()`. Core algorithm (lat/lon -> pgid, date -> month_index) could be extracted into a pure function. **Update 2026-05-21 (ADR-031 review):** Renamed from `_place_events_columnar` — the old name falsely claimed columnar processing. The function receives Python lists from `.to_pylist()` and iterates row-by-row. The underlying P1 violation (`.to_pylist()` materialization) remains tracked in C-144. **Trigger: extract `compute_bin_assignments()` when compilation tests exceed 5 seconds.**
**Source:** Feathers (expert review #4), ADR-031 compliance review (2026-05-21). Cross-ref: C-144, C-74.

### C-79: Compilation/consolidation require real Parquet I/O in tests — [DEFER]
`compile_grid()` and `consolidate_ucdp()` always read from disk. No seam to inject mock reader. Tests create actual Parquet files. **Trigger: add `read_table_fn` parameter when test suite exceeds 30 seconds.**
**Source:** Feathers (expert review #4)

### ~~C-115: Summary detection threshold (>= vs >) is architectural~~ DEMOTED
Demoted to tech-debt backlog 2026-05-28 (review-rr strategic curation). Threshold is documented in ADR-023 and matches VIEWSER. No evidence of UCDP or VIEWSER changing this. Re-register if threshold changes.
**Source:** Parity investigation 2026-04-08, notebook archaeology (GED_loader{0,1,2}.ipynb).

### C-116: No retry on remote zarr network failures — [DEFER]
`_load_grid_from_zarr` in `dataset.py` opens a remote zarr store via xarray/fsspec/aiohttp. Transient network errors (DNS timeout, TCP reset, server restart) fail immediately — no retry, no backoff. `datafactory_http.retry.request_with_retry()` exists but is designed for `requests`-based harvester calls, not the xarray/fsspec path. For consumers, a transient failure at 2am during automated training means a full pipeline retry. **Trigger: consumer reports intermittent failures loading remote data.** Cross-ref: C-70 (circuit breaker, harvester path).
**Source:** Expert review #5 (M12 investigation), Nygard perspective, 2026-04-08.

### C-117: Remote zarr downloads all spatial cells before region filter — [DEFER]
`_load_grid_from_zarr` applies temporal and feature subsetting lazily (xarray isel/variable selection), but spatial subsetting (region → pgid set) happens AFTER full grid materialization in `load_dataset`. For remote stores, this means downloading all 259,200 cells even when only ~13,000 are needed (e.g., Africa). The spatial dimension is 360x720 per time step per feature — less impactful than temporal (which IS subsetted), but still ~20x more data than needed for typical region queries. xarray does not support efficient irregular spatial selection on chunked stores without rechunking. **Trigger: consumer queries a single country over a slow connection and complains about latency.**
**Source:** Expert review #5 (M12 investigation), Kleppmann perspective, 2026-04-08.

### C-97: Basic auth + Caddy scalability ceiling at ~30-50 users — [DEFER]
Caddy's `basic_auth` stores username/bcrypt-hash pairs in a flat Caddyfile. No audit trail (who accessed what, when), no per-user rate limiting, no credential rotation, no MFA. Acceptable for a small research team (5-20 users). Breaks down at 30-50 users when credential management, audit requirements, and revocation coordination become operational burdens. Migration path: Caddy `forward-auth` directive + oauth2-proxy with institutional SSO (PRIO/Uppsala). **Trigger: before consumer count exceeds 30, or before institutional audit/compliance requirements emerge.**
**Source:** Falsification audit 2026-04-01 (F2)

### ~~C-135: No runtime type validation for zarr `.zattrs` values~~ DEMOTED
Demoted to tech-debt backlog 2026-05-28 (review-rr strategic curation). Only risk vector is manual server-side editing of `.zattrs`, which is unlikely. Our code writes correct types. Re-register if external consumers can write attrs.
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
| Trigger | Before 6th pipeline source (WDI) requires a verify script, or when shared verify framework is prioritized in refactor sprint. Previous trigger (5th source, V-Dem) resolved 2026-05-26. |
| Location | `scripts/visualize_audit.py` (UCDP), `scripts/verify_acled_grid.py` (ACLED), `scripts/verify_ghspop_grid.py` (GHS-POP), `scripts/verify_ghsbuilts_grid.py` (GHS-BUILT-S), `scripts/viz_style.py` (shared aesthetics only) |

Each data source has its own plotting/audit script with duplicated structural patterns: `PrecomputedData` dataclass, single-pass `precompute()`, `cell_to_label()`, `REGION_BOUNDS`, per-plot functions, and statistical pass/fail checks. The scripts share `viz_style.py` for aesthetic constants and helpers (`spatial_imshow`, `style_ax`, `save_plot`) but nothing for plot structure, check logic, or report generation.

**Note (2026-05-20):** Trigger condition met — GHS-POP is the third visual audit script. The three scripts share structural patterns but differ in domain-specific checks (population density vs. fatality rates vs. event counts). Accepted for now: three scripts is enough to see the abstraction clearly, but the abstraction is moderate complexity (pluggable feature specs, check definitions, report generation). Consider extraction when 4th source arrives. Cross-ref: C-164 (WET inventory).
**Note (2026-05-22):** GHS-BUILT-S added as 4th data source. Falsification audit proved total absence of visual audit capability — 5/5 probes hard-falsified. Escalated from Tier 4 DEFER to Tier 2.
**Note (2026-05-22):** C-155 remediated — `verify_ghsbuilts_grid.py` created (10 plots, 6 statistical checks), `--verify` flag added to pipeline, falsification stubs F1-F3 flipped. Full pipeline run successful with all checks PASS. Demoted back to Tier 4 DEFER — the original idiosyncrasy concern (4 bespoke scripts) remains but is not acute. Reassess at 5th source.

**Note (2026-05-24, repo-assimilation v1.2.20):** Quantified: 4 verification scripts total 2,804 lines (UCDP 1,015, GHS-POP 811, GHS-BUILT-S 978, ACLED not counted separately). ~60% structural overlap across scripts (`PrecomputedData` dataclass, `precompute()`, `cell_to_label()`, `REGION_BOUNDS`, per-plot functions, statistical pass/fail checks). At source #5, the extraction cost (~2 days) will be less than the duplication cost (~1 day per copy + ongoing maintenance).

**Note (2026-05-26, review-rr strategic):** V-Dem (5th pipeline source) added without verify script — trigger fired. V-Dem data is country-level democracy indicators (not spatial raster), so the existing raster-oriented verify framework doesn't directly apply. A V-Dem verify script would need different checks (ISO3 coverage, NaN rates, annual→monthly step-function verification). Cross-ref: C-204 (V-Dem has zero falsification files).

**Note (2026-05-26, review-rr strategic curation):** V-Dem verify script created (`scripts/verify_vdem_grid.py`, 15 plots), resolving the "5th source, no verify script" trigger. Underlying concern remains: 5 bespoke verify scripts (UCDP 1,015 lines, GHS-POP 811 lines, GHS-BUILT-S 978 lines, ACLED ~600 lines, V-Dem ~1,770 lines = ~5,174 lines total) with ~60% structural overlap. Trigger updated to 6th source (WDI).

See also C-44 (harvest pipeline template — same WET-before-DRY decision), C-154 (ACLED feature config duplication), C-164 (cross-layer WET inventory), C-195 (falsification test accumulation).

### C-164: Cross-layer WET debt — 6 sources replicate patterns across all 4 layers — [TRIGGER FIRED]

| Field | Value |
|-------|-------|
| ID | C-164 |
| Tier | 3 |
| Source | WET-before-DRY audit (2026-05-19), GHS-POP Phase 4 completion, expert code review (2026-05-30) |
| Trigger | **Fired 2026-05-22 (GHS-BUILT-S), 2026-05-26 (V-Dem), 2026-05-29 (SHDI):** 6th pipeline source copied cross-layer patterns without extraction. Before WDI integration or next data source. |
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

Cross-ref: C-44 (harvest pipeline template), C-07 (frozen dataclass pattern), C-155 (visual audit framework), C-06 (provenance composability), C-219 (PrecomputedData CIC).

**Note (2026-05-26, visual audit docs falsification):** Beyond code duplication, the verification scripts also lack governance: no ADR, CIC, or standard defines what a verification script must check, how plots are selected, or what "PASS" means. ADR-005 covers unit/integration tests. ADR-019 covers aesthetics. Neither covers visual audit methodology. When extraction happens, a verification standard should accompany it.

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

**Note (2026-05-26, review-rr strategic):** V-Dem (9th source, 5th pipeline source) added — replicated harvest, viewpoint, compilation, pipeline runner, and harvest wrapper patterns. V-Dem viewpoint uses ISO3→pgid crosswalk (new pattern, not raster-based), so raster-specific extractions (patterns already done in v1.2.21) don't apply. Remaining unextracted patterns (1, 3, 7, 8) were each copied one more time. Total: 5 pipeline sources replicating 5 remaining patterns = 25 pattern copies.

**Note (2026-05-28, review-rr strategic curation):** C-44 merged into this entry. C-44 (harvest pipeline template) was a subset covering only the harvest layer; its 9 accumulated notes tracked each source addition. The harvest template gap is covered here as patterns #1 (harvester config validators) and #8 (harvest script wrappers). C-183 was previously merged into C-44, and now transitively merges here.

**Note (2026-05-30, expert code review C-164):** SHDI (10th source, 6th pipeline source) added — replicated all remaining unextracted patterns. Deep audit quantified actual pattern scope:
- Pattern #1: 10 config classes (not 5) with `__post_init__` validation: `ucdp_annual.py`, `ucdp_candidate.py`, `ucdp_dot9.py`, `acled.py`, `ghspop.py`, `ghsbuilts.py`, `priogrid_static.py`, `gaul_admin.py`, `vdem.py`, `shdi.py`. `timeout < 1` check appears in all 10.
- Pattern #3: 5 viewpoint builders (not 3-4): `ucdp_v1.py`, `acled_v1.py`, `ghspop_v1.py`, `ghsbuilts_v1.py`, `vdem_v1.py`. All share config-or-shortcut entry point + `append_ledger_entry` with `LEDGER_VERSION`/`DIGEST_SCHEME`.
- Pattern #7: 4 pipeline runners (not 3): `run_acled_pipeline.py`, `run_ghspop_pipeline.py`, `run_ghsbuilts_pipeline.py`, `run_vdem_pipeline.py`. All use `STEPS.index(args.skip_to)` + `if skip_idx < N` pattern. Total 1,093 lines.
- Pattern #8: 9 harvest scripts (not 7): `harvest_ucdp.py`, `harvest_acled.py`, `harvest_ghspop.py`, `harvest_ghsbuilts.py`, `harvest_priogrid.py`, `harvest_gaul.py`, `harvest_shapefile.py`, `harvest_vdem.py`, `harvest_shdi.py`. Total 1,185 lines of argparse + banner + timing boilerplate.
- Pattern #6: 87 provenance call sites in `/src` (47 `append_ledger_entry`, 16 `last_digest_for_version`, 10 `compute_content_digest`, 9 `compute_file_digest`, 5 other).

Total: 6 sources × 5 remaining patterns = 30 pattern copies, 8,537 lines in pattern-affected files.

Extraction risks identified (failure mode analysis):
- FM-1 (Pattern #1): Extracted validator could produce wrong field name in error message → mitigated by TDD (test error message includes field name).
- FM-2 (Pattern #8): Shared HarvestRunner could change exit codes → mitigated by characterization tests before extraction.
- FM-3 (Pattern #7): Shared PipelineRunner could change `--skip-to` precondition checking → mitigated by source-specific preconditions declared per pipeline.
- FM-4 (Pattern #3): Config-or-shortcut resolution varies (V-Dem accepts 2 shortcuts, others accept 1) → mitigated by per-config `@classmethod from_shortcuts()`.

Recommended extraction order (TDD): #1 (config validators, trivial, low risk) → #8 (harvest wrappers, moderate, characterize first) → #7 (pipeline runners, moderate) → #3 (viewpoint scaffolding, low risk but low payoff) → #6 (provenance, HIGH risk, DEFER to C-06).

**Source:** WET-before-DRY inventory audit after GHS-POP Phase 4 completion (2026-05-19), updated GHS-BUILT-S (2026-05-22), tech-debt-cleanup investigation (2026-05-24), v1.2.21 maintenance sprint (2026-05-25), expert code review C-164 (2026-05-30).

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

### ~~C-109: Advisory file locks (fcntl) don't work across NFS~~ DEMOTED
Demoted to tech-debt backlog 2026-05-28 (review-rr strategic curation). NFS migration is hypothetical; server uses local NVMe SSD. Re-register if multi-server deployment is planned.
**Source:** Repo assimilation 2026-04-04 (Phase 5, invariant 10). DDIA Ch.7 pp.234-236, Ch.8 pp.301-303.

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

### ~~C-160: ACLED `fetch_paginated` string-data corruption has no guard~~ DEMOTED
Demoted to tech-debt backlog 2026-05-28 (review-rr strategic curation). Downstream `validate_events` catches this; type guard at fetch layer is defense-in-depth, not load-bearing. Re-register if validation layer is refactored.
**Source:** ACLED test review (2026-05-07). Cross-ref: C-153.

### C-173: Hetzner server memory headroom — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-173 |
| Tier | 3 |
| Source | Falsification audit + 8-expert code review (2026-05-20) |
| Trigger | Any transient memory spike above physical RAM during pipeline execution on the Hetzner server |
| Location | Hetzner CPX32 server configuration, `docs/guides/hetzner_deployment_guide.md` (troubleshooting section) |

**Update 2026-05-28 (review-rr strategic curation):** Server rescaled to CPX42 (16 GB RAM) + 16 GB swap = 32 GB total (confirmed during v1.2.22 deployment). V-Dem compilation (9.7 GB), assembly (35.5 GB on mmap), and zarr export all completed successfully. Tier recalibrated 3→4: the immediate risk (OOM on 8 GB) is resolved; remaining concern is architectural (R&D plan for bounded-memory compilation at `reports/rd_plan_bounded_memory_compilation.md`).

The Hetzner CPX32 (8 GB RAM) has no swap partition or swapfile. Without swap, the Linux OOM killer is the only backstop — any process that exceeds available RAM is killed immediately (exit code 137) with no chance to degrade gracefully. The GHS-POP viewpoint loads a 6.88 GiB GeoTIFF array, leaving ~600 MB headroom for Python, tifffile buffers, and OS services. A 2 GB swapfile would convert hard kills into degraded performance. Swap setup documented in deployment guide troubleshooting section (v1.2.18). Cross-ref: C-165 (original OOM), C-170 (list accumulation OOM), C-88 (server hardening).

### ~~C-184: ACLED `_year_is_cached` checks file existence, not file integrity~~ — [RESOLVED]

Resolved 2026-06-02 (PR #98, v1.2.25). `_year_is_cached` now calls `_recompute_content_digest(snap_path)` which reads the Parquet file, extracts digest fields, and recomputes `content_digest` using the same algorithm as `event_validation.py`. Returns `None` on corrupted/unreadable files (ArrowInvalid, OSError), triggering cache miss. Superseded by C-232 (digest type mismatch) which was the actual root cause — the original C-184 recommendation to use `compute_file_digest` would not have worked because the ledger stores `content_digest`, not `file_digest`.

Cross-ref: C-232 (root cause), C-185 (GHS-POP — NOT affected, verified by falsification audit).

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
| Tier | 4 (recalibrated from 3 during strategic curation 2026-05-28) |
| Source | Falsification audit — coverage parity (2026-05-22) |
| Trigger | GHS-BUILT-S encounters a production incident on Hetzner that would have been caught by Red-team or falsification tests present for GHS-POP but absent for GHS-BUILT-S |
| Location | `tests/test_ghsbuilts_harvester.py`, `tests/test_ghsbuilts_viewpoint.py`, `tests/test_ghsbuilts_compilation.py`; parity stubs in `tests/test_falsification_ghsbuilts_coverage_parity.py` |

GHS-BUILT-S test suite has 41 test functions vs 215 for ACLED + GHS-POP + PRIO-GRID/GAUL combined (19%). Five specific gaps: (F1) 41 vs 215 test functions, (F2) 86 vs 368 assertions, (F3) 1 vs 10 Red-team classes — viewpoint and compilation have zero adversarial tests, (F4) 0 vs 7 dedicated falsification test files — GHS-POP has 4 (deploy v1/v2/v3, memory), (F5) viewpoint tests are 441 lines vs GHS-POP viewpoint alone at 937 lines. Root cause: WET-before-DRY replication correctly duplicated production code but not the accumulated test and audit investment from GHS-POP's five PRs and four OOM-fix cycles. Parity stubs are `xfail strict=True` and will break when thresholds are met.

Cross-ref: C-164 (WET-before-DRY raster code duplication), C-180 (no falsification tests for non-GHS-POP compilation/viewpoint paths).

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


### D-26: Discovery probing cost vs cache staleness (UCDP candidate/dot9)

Nygard argues the 98+ discovery probes per run are a reliability risk: if UCDP starts rate-limiting, the pipeline fails before any useful work. A discovery cache (persist known versions, probe only the frontier) reduces API calls from 98+ to 1-3. Kleppmann counters that a discovery cache introduces a staleness window: if UCDP retracts a version or changes the available set, the cache would serve stale metadata. Beck notes the current approach "works fine" and the optimization should wait for evidence of rate-limiting. **No resolution yet — monitor for rate-limiting before investing in a discovery cache.**

**Source:** Expert code review of harvest caching (2026-05-21). Cross-ref: C-181 (discovery probing).

### D-29: Shapefile harvester retrofit depth — full outcome compliance vs organic

Nygard and Martin argue for full outcome-vocabulary compliance now (add try/except, record `"failed"` entries, use `"outcome": "success"/"unchanged"`). Feathers and Beck argue the current code works correctly via backward compat and the retrofit should happen organically when the shapefile harvester is next touched or when V-Dem is added. Hickey notes `"changed": True/False` is accidental complexity but not dangerous. **Trigger: when shapefile harvester is next touched for a bug fix, or when V-Dem requires shapefile-like ingestion (trigger rewritten during review-rr 2026-05-24). No resolution yet — the shapefile harvester is rarely touched (one-time artifact).**

**Source:** Expert code review of provenance/shapefile (2026-05-21). Cross-ref: C-186 (shapefile lacks outcome vocabulary), C-44 (harvest pipeline template).

### C-195: 37 falsification test files accumulated without curation (3,129 lines) — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-195 |
| Tier | 4 |
| Source | repo-assimilation v1.2.20 (2026-05-24) |
| Trigger | Next audit round adds files, or total exceeds 45 — consolidation then reduces navigation cost (trigger rewritten during review-rr 2026-05-26) |
| Location | `tests/test_falsification_*.py` (37 files, 3,129 lines, 129 test functions) |

Falsification audits produce `test_falsification_*.py` files containing failing test stubs that flip green after fixes. Over 10+ audit rounds (GHS-POP memory, coverage parity, visual audit, merge-readiness ×2, deployment ×2, plus earlier UCDP/ACLED audits), 37 files have accumulated. Many test stubs target concerns that are now resolved (C-190, C-191, C-193, C-194) — their stubs pass but serve no ongoing purpose beyond documentation that the fix exists. The test files are not consolidated by concern or source: `test_falsification_ghsbuilts_coverage_parity.py`, `test_falsification_ghsbuilts_merge_ready.py`, `test_falsification_ghsbuilts_deploy_v2.py` all test overlapping aspects of GHS-BUILT-S readiness. Curation options: (a) archive resolved stubs into a `tests/archive/` directory, (b) consolidate per-source stubs into one file per source, (c) tag resolved stubs with `@pytest.mark.resolved` and skip in CI. Tier 4 because: (a) all tests pass, (b) no correctness impact, (c) single-developer scope, (d) the accumulation is a navigation and maintenance burden, not a risk.

**Note (2026-05-26, review-rr strategic):** V-Dem added 0 falsification files (opposite extreme from GHS-BUILT-S at 12 files). The prediction "5th source adds 5-8 files" was wrong — C-204 tracks the V-Dem gap separately. File count remains at 37.

Cross-ref: C-189 (GHS-BUILT-S coverage parity gap), C-180 (no falsification for non-GHS-POP paths), C-164 (WET-before-DRY broader inventory), C-204 (V-Dem zero falsification files).

### C-223: Compilation pipeline allocates full grid in RAM — [R&D PLANNED]

| Field | Value |
|-------|-------|
| ID | C-223 |
| Tier | 3 |
| Source | Expert code review (memory scalability, 2026-05-28), review-rr strategic blind spot |
| Trigger | Next data source (WDI: 20-50 features) pushes single-source compile past 16 GB, or total assembled features exceed 100 |
| Location | `src/datafactory_compilation/pregridded_compilation.py:171` (`np.full()`), `src/datafactory_compilation/grid_compilation.py:224` (`np.full()`), `scripts/export_zarr.py:120` (`np.asarray()`) |

`compile_pregridded()` and `compile_grid()` allocate the entire output grid as a single in-memory array via `np.full()`. V-Dem (22 features) requires 9.7 GB; the full 75-feature assembly requires 35.5 GB. Each new data source adds features, and each year adds 12 time steps. The assembly step already uses `open_memmap()` (proven pattern at `assemble_grid.py:491`), but the compilation step does not.

**R&D plan:** `reports/rd_plan_bounded_memory_compilation.md` — 4 steps: (1) replace `np.full()` with `open_memmap()` in both compilation functions, (2) add pre-flight disk space checks, (3) remove `np.asarray()` in zarr export, (4) ADR documenting the bounded-memory decision. Estimated effort: ~8 hours. Success criterion: V-Dem compiles in < 1 GB peak RSS.

Cross-ref: C-144 (compilation to_pydict), C-145 (viewpoint full store load), C-173 (server memory headroom), D-24 (hardware vs software — resolved: both).

---

### ~~C-225: SHDI version drift in docs — "v8.3" in two files, code defaults to "v10.2" (Resolved 2026-05-29)~~ RESOLVED

Both version strings corrected to "v10.2" in `docs/ADRs/README.md:135` and `docs/guides/consumer_data_guide.md:421`.

### ~~C-226: SHDI shapefile download failure writes no ledger entry (Resolved 2026-05-29)~~ RESOLVED

Try/except added around shapefile download with `"failed"` ledger entry before re-raise (shdi.py:331-348).

### ~~C-227: SHDI `_parse_and_merge` inner join can silently drop rows (Resolved 2026-05-29)~~ RESOLVED

Added fail-loud row-count guard in `_parse_and_merge` (`shdi.py:478-490`): after each inner join step, compares `result.num_rows` against `expected_rows`. If any rows are lost, logs error with percentage and raises `ValueError` with "coverage mismatch" message. Test: `test_indicator_row_mismatch_raises`. Live API confirmed all 4 indicators have identical 62,531-row key sets — guard passes today, will fire if GDL changes.

### ~~C-228: Dead `download_url` property on `ShdiConfig` (Resolved 2026-05-29)~~ RESOLVED

Removed `download_url` property from `ShdiConfig` and replaced `test_download_url_includes_indicators` with `test_indicator_url_includes_variable`.

### ~~C-229: `docs/sources/shdi.md` claims "1 request per run" (Resolved 2026-05-29)~~ RESOLVED

Updated to "5 requests per run — one per indicator plus shapefile."

### C-224: No server backup or disaster recovery plan — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-224 |
| Tier | 4 |
| Source | review-rr strategic blind spot (2026-05-28) |
| Trigger | Disk failure, accidental `rm -rf`, or Hetzner datacenter incident causes data loss |
| Location | Hetzner server `/home/views-deploy/views-datafactory/data/` (raw, consolidated, compiled, assembled) |

The Hetzner server stores all pipeline data (raw harvests, consolidated stores, compiled grids, assembled output) on a single NVMe disk with no backup, snapshot, or disaster recovery plan. All data is rebuildable from source APIs (UCDP, ACLED, JRC, V-Dem), but a full rebuild from scratch takes ~8-12 hours and requires all API credentials. Hetzner Cloud offers automated snapshots (~€0.01/GB/month) and Volumes for incremental backups. The `data/raw/` directory is the highest-value target — everything downstream is derived.

Cross-ref: C-88 (SSH access control), C-131 (no external monitoring).

### C-230: Script layer (harvest + pipeline) has zero unit tests — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-230 |
| Tier | 4 |
| Source | Expert code review of C-164 (2026-05-30), Feathers and Beck perspectives |
| Trigger | Harvest script or pipeline runner refactoring (Pattern #7/#8 extraction) changes exit codes, banner format, or `--skip-to` behavior with no test to catch the regression |
| Location | `scripts/harvest_*.py` (9 files, 1,185 lines), `scripts/run_*_pipeline.py` (4 files, 1,093 lines) |

The 9 harvest scripts and 4 pipeline runners have zero unit tests. The scripts are tested only via integration (running the full pipeline on a live server). There are no tests for: correct argument forwarding (`--force` → `force_refresh=True`), exit code semantics (0 on success, 1 on failure), `--skip-to` precondition checking (file existence before skipping), or banner output correctness. This is the largest untested surface in the codebase (2,278 lines, 13 files). When Pattern #8 and #7 extraction begins, characterization tests must be written FIRST to capture current behavior before refactoring. Tier 4 because: (a) scripts are thin wrappers with most logic in the tested source modules, (b) single-developer project, (c) no correctness risk from script bugs beyond operational inconvenience.

Cross-ref: C-164 (WET-before-DRY — patterns #7 and #8), C-180 (no falsification tests for non-GHS-POP paths), C-189 (test coverage parity gap).

### C-236: Status page artifact mapping requires manual update per source — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-236 |
| Tier | 4 |
| Source | expert-code-review (2026-06-03), Feathers + Ousterhout perspectives |
| Trigger | Next source integration (e.g., WDI) adds source to registry and pipeline but omits artifact mapping in `generate_status.py` |
| Location | `scripts/generate_status.py` (proposed — artifact path mapping dict) |

The status page will contain a hardcoded mapping from source names to artifact paths per pipeline stage. This mapping must be manually updated whenever a new source is integrated. The same pipeline-path information also exists in `docs/guides/data_source_integration_guide.md:22-25`, `refresh_pipeline.sh` (implicit in step ordering), and `test_operational_integration.py:22-28` (exclusion list). Four locations for the same information is an information leakage risk. Tier 4 because: (a) single-developer project, (b) impact is "wrong status page" not "wrong data," (c) the status page itself can derive some answers from filesystem state.

Long-term mitigation: standardize artifact output paths by convention (e.g., `data/compiled/{source_id}/grid.npy`) so the status page derives paths instead of hardcoding them. Short-term: add a test that all sources with features in the registry have an entry in the artifact mapping.

Cross-ref: C-164 (cross-layer WET debt), C-155 (no shared verify framework), D-33 (pipeline-path location). GitHub: #101, #102.

### C-240: generate_status.py docstring specifies nonexistent /www/ path — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-240 |
| Tier | 4 |
| Source | falsification audit (2026-06-04, G1) |
| Trigger | Developer reads `generate_status.py` docstring (line 9) and uses the usage example `--output /srv/views-data/www/status.html` verbatim |
| Location | `scripts/generate_status.py:9` (docstring usage example) |

The script's docstring shows `--output /srv/views-data/www/status.html` as the example invocation. The `/www/` subdirectory appears in no other document — not in ADR-038, the deployment guide, #104, or `refresh_pipeline.sh`. It is a fabricated path. The actual deployment uses `data/status.html` (relative to repo root, symlinked to `/srv/views-data/status.html`). A developer following the script's own documentation would write to a nonexistent directory. Tier 4 because: (a) `mkdir(parents=True)` on line 431 would silently create the `/www/` directory, so the script wouldn't error, but the file would land where no one expects, (b) no automated process reads the docstring, (c) single-developer scope.

**Resolution:** Update docstring to match actual usage: `--output data/status.html`.

Cross-ref: C-239 (#104 path disagreement), C-238 (stale #104 Caddy claims).

### C-241: No invariant for intensive feature conservation across resolution or aggregation — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-241 |
| Tier | 4 |
| Source | ADR-040 scoping discussion (2026-06-05) |
| Trigger | First consumer aggregates intensive features (HDI, built-up fraction, democracy scores) to country-month level, or grid resolution changes from 0.5° to a finer scale |
| Location | `src/datafactory_adapters/grid_to_country_month.py` (aggregation path), ADR-040 (explicit scope exclusion) |

ADR-040 establishes count conservation (Invariant 1) and hierarchical reconciliation (Invariant 2) for extensive quantities — fatalities, event counts, population counts — where sums must balance across layers and aggregation levels. Intensive features (V-Dem democracy scores, SHDI human development index, GHS-BUILT-S built-up surface fraction) are explicitly out of scope because sums are not meaningful for these quantities. There is no ADR and no defined invariant for how intensive features should behave under aggregation (area-weighted average? population-weighted average?) or when grid resolution changes (does a 0.25° cell inherit its parent 0.5° cell's value? does it interpolate?).

Currently this is not acute: `grid_to_country_month.py` sums all features including intensive ones (line 115), which is mathematically wrong for HDI and democracy scores but harmless because no downstream consumer currently uses country-month intensive feature totals. The problem becomes acute when: (a) a model or consumer aggregates V-Dem or SHDI to country-month and interprets the sum as meaningful, or (b) grid resolution changes and intensive features must be resampled. Both scenarios require defining what "conservation" means for non-additive quantities — likely area-weighted or population-weighted averaging, which is a research decision, not an engineering one.

**Resolution:** Write a future ADR defining intensive feature aggregation semantics when a concrete consumer requires it. Until then, ADR-040's explicit exclusion of intensive features serves as the documented gap.

Cross-ref: ADR-040 (scope boundary table, "Intensive feature conservation"), ADR-024 (Invariant 6: country-level broadcast for V-Dem), ADR-035 (GHS-BUILT-S integration).

### C-244: 4 CICs + ADR-025 not updated after ADR-040 acceptance

| Field | Value |
|-------|-------|
| ID | C-244 |
| Tier | 4 |
| Source | review-base-docs (2026-06-05) |
| Trigger | Investigation branch merges to development without updating the 4 CICs and ADR-025 to reference ADR-040 |
| Location | `docs/CICs/grid_to_country_month.md` (Related ADRs, Section 3), `docs/CICs/CompilationConfig.md` (Related ADRs, Section 3), `docs/CICs/AssemblyConfig.md` (Related ADRs, Section 3), `docs/CICs/GaulAdminConfig.md` (Related ADRs, Section 3, Section 10), `docs/ADRs/025_country_identity_gaul.md` (lines 96-102, references) |

ADR-040 (accepted 2026-06-05) establishes two constitutional invariants affecting all pipeline layer boundaries. Four CICs governing the stages where these invariants apply do not reference ADR-040 and do not include the mandated guarantees in their Section 3 contracts: grid_to_country_month (missing conservation equation), CompilationConfig (missing accounting equation), AssemblyConfig (missing cell-loss guarantee), GaulAdminConfig (missing hierarchical consistency, Section 10 still says "Tests: not yet written"). ADR-025, which ADR-040 builds on extensively, does not back-reference ADR-040. A developer consulting these CICs would not know count conservation is architecturally required at their layer boundary.

**Resolution:** Batch-update all 5 documents in a single commit: add ADR-040 to Related ADRs, add conservation guarantees to Section 3, update Section 10 test alignment. Documentation-only change with zero code risk.

Cross-ref: C-242 (conservation assertions untested), C-243 (hierarchical reconciliation untested), ADR-040.

### C-231: No compilation idempotence guard — silent recompilation with stale inputs — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-231 |
| Tier | 4 |
| Source | Expert code review of C-164 (2026-05-30), Kleppmann perspective |
| Trigger | Operator re-runs compilation after viewpoint is re-built with different parameters, producing a grid from mixed-vintage inputs without warning |
| Location | `src/datafactory_compilation/grid_compilation.py` (`compile_grid`), `src/datafactory_compilation/pregridded_compilation.py` (`compile_pregridded`), `src/datafactory_compilation/output.py` (`write_compilation_output`) |

`compile_grid()` and `compile_pregridded()` always overwrite the output directory. If run twice with different inputs (e.g., viewpoint was re-built between runs with different parameters), there is no warning that the input context changed. The provenance ledger records what happened, but nothing reads the ledger to check input consistency before writing. A pre-compilation digest check — compute digests of all input files, compare against the previous compilation's input digests in the ledger — would be cheap and would catch accidental recompilation with stale or mixed inputs. Tier 4 because: (a) single-operator deployment, (b) the pipeline script runs steps in order so mixed inputs are unlikely, (c) provenance provides post-hoc audit capability.

Cross-ref: C-223 (compilation memory — same functions, different concern), C-46 (no ledger write idempotency).

### ~~C-232: ACLED cache digest type mismatch — `compute_file_digest` vs `content_digest`~~ — [RESOLVED]

| Field | Value |
|-------|-------|
| ID | C-232 |
| Tier | 1 (silent data waste — every pipeline run re-downloaded all ACLED data) |
| Source | Expert code review of digest verification (2026-06-02), 3 falsification audits |
| Trigger | Every pipeline run (trigger was permanently fired from commit `43b5625` through v1.2.24) |
| Location | `src/datafactory_harvester/sources/acled.py:431` (`_year_is_cached`) |

`_year_is_cached()` compared `compute_file_digest(snap_path)` (SHA-256 of Parquet file bytes) against `content_digest` from the ledger (SHA-256 of sorted event tuples serialized as JSON via `event_validation.py:196-201`). For Parquet files, these are fundamentally different values — they can never match. Every pipeline run re-downloaded all ACLED data (~2M events, 6 years, 2400+ API requests per year). Introduced in commit `43b5625` (PR #91, v1.2.23). The expert code review initially claimed GHS-POP and GHS-BUILT-S were also affected (C-195 splash zone), but 3 falsification rounds proved only ACLED is broken — TIF-based harvesters write raw bytes to disk, so `compute_file_digest(path) == compute_content_digest(data)`.

**Resolved 2026-06-02 (PR #98, v1.2.25).** Fix: added `_recompute_content_digest()` which reads the Parquet back, extracts digest fields, and recomputes `content_digest` using the same algorithm. Catches `ArrowInvalid`/`OSError` on corrupted files, returning `None` (cache miss). 14 new tests, 3 falsification audits, 0 regressions (1504 tests pass). Issues: #94 (fix), #95 (non-atomic writes, deferred), #96 (latent risk in 7 other harvesters, deferred), #97 (archive subdirectory, deferred).

Cross-ref: C-184 (superseded — original recommendation to use `compute_file_digest` would not have worked), C-185 (GHS-POP — NOT affected).

### D-30: Config validator extraction depth — utility functions vs declarative specs

Martin/Beck advocate extracting simple utility functions (`validate_positive_int(value, name)`) that configs call in their `__post_init__`. Each config retains its `__post_init__` method but delegates to shared validators. This preserves the existing seam, is easy to TDD, and follows the proven extraction precedent (`raster_io.py`, `temporal.py`). Hickey advocates a declarative validation spec where configs declare constraints as data and a single generic validator applies them, eliminating `__post_init__` entirely for standard constraints. The declarative approach is more elegant but harder to reverse: once configs drop their `__post_init__`, re-adding them requires touching every config class. **Recommendation: start with utility functions (lower risk, reversible), promote to declarative specs only if utility approach still feels repetitive at 12+ sources.**

**Source:** Expert code review of C-164 (2026-05-30). Cross-ref: C-07 (frozen dataclass pattern), C-164 (pattern #1).

### D-31: Harvest script consolidation — single unified script vs thin delegates

Ousterhout argues the 9 harvest scripts should be merged into one deep `harvest.py` with `--source acled|vdem|shdi|...` dispatch via the existing Registry. The scripts are shallow modules (pure boilerplate) and 9 copies of a shallow module is worse than 1. Nygard counters that a single script creates a single failure domain — a bug in shared argparse handling blocks all 9 sources. Feathers proposes a middle path: extract a shared `HarvestRunner` function, but keep source-specific scripts as 5-10 line thin delegates that call it. This satisfies both deep-module design (Ousterhout) and blast-radius isolation (Nygard). **No resolution yet — the middle path (shared runner + thin delegates) appears to be the pragmatic choice, but extraction hasn't started.**

**Source:** Expert code review of C-164 (2026-05-30). Cross-ref: C-164 (pattern #8), C-230 (script layer zero tests).

### ~~D-32~~: `assembled` flag vs removing features from partially-integrated sources — Resolved #105

**Positions:**

- **Add `assembled: bool` to `SourceEntry`** (#103 proposal): SHDI keeps its features in the registry but gets `assembled=False`. `get_all_features()` filters by default. Pro: registry remains a planning document; features are declared even before code exists. Con: adds a second source of truth (flag vs filesystem); flag can drift from reality; every `get_all_features()` caller must understand the default.

- **Remove SHDI features and phantom downstream entries** (Martin, Hickey, Kleppmann): Delete SHDI's `features` tuple and the SHDI Viewpoint / SHDI Compilation entries from `PIPELINE_SOURCES`. Re-add when code exists. Pro: zero code changes to `get_all_features()`; registry stops lying; simpler. Con: registry loses its planning role; source exists in registry with no features (confusing?).

- **Create separate function `get_assembled_features()`** (Kleppmann): Leave `get_all_features()` unchanged (returns all 79). Add a new function for consumers that need only assembled features. Pro: no breaking change, explicit semantics. Con: two functions for overlapping concepts.

**Key tension:** Is the source registry a planning document or a deployment document? The `assembled` flag says both; removing features says deployment-only. The answer determines whether future sources should be declared before or after their code is written.

**Source:** expert-code-review (2026-06-03). Cross-ref: C-235, D-30 (config validator depth).

### D-33: Pipeline-path information — registry field vs standalone mapping vs convention

**Positions:**

- **Add `pipeline_path` field to `SourceEntry`** (Ousterhout, GoF): An enum or literal `"event" | "raster" | "static"` on the harvest-level entry. One source of truth. `generate_status.py`, `test_operational_integration.py`, and future tools derive behavior from it. Pro: eliminates information leakage across 4 files. Con: registry grows; pipeline path is a reporting/operational concern, not a data-model concern.

- **Keep as standalone mapping in `generate_status.py`** (plan proposal, WET-before-DRY): The status page script owns its own mapping. Extract to registry only when a second consumer needs it. Pro: keeps registry simple; one consumer, one mapping. Con: mapping will drift; `test_operational_integration.py` already needs the same information and hardcodes its own version.

- **Derive from conventions** (Hickey): Standardize artifact paths (`data/compiled/{source_id}/grid.npy`). The status page probes predictable paths instead of maintaining a mapping. Pro: zero maintenance; self-healing. Con: requires all sources to follow the convention (they currently don't); retrofit cost.

**Source:** expert-code-review (2026-06-03). Cross-ref: C-236 (artifact mapping maintenance), C-164 (cross-layer WET).

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
14 config classes (10 harvester + 4 viewpoint) follow the same frozen-dataclass-with-`__post_init__` pattern. No shared Protocol or base. A declarative validation approach or `ValidatedConfig` Protocol would reduce duplication. Kleppmann (Ch.4 p.127) argues schemas serve as documentation that "cannot diverge from reality" — our frozen dataclasses with `__post_init__` validation are effectively runtime schemas. **Accepted: explicit repetition is simple and readable; each config is its own schema.** See D-30 for the utility-functions vs declarative-specs disagreement.
**Source:** Hickey. DDIA Ch.4 p.127. Updated: expert code review C-164 (2026-05-30).

### C-32: Source registry returns `Any`
`fetch_source` returns `Any` (widened from `Path` for candidate's `list[dict]`). Sources, consolidators, and builders are intentionally heterogeneous — each has a different signature. The three strategy registries (aggregation, survivorship, temporal_distribution) already use precise types. Kleppmann (Ch.4 p.126) notes dynamically generated schemas are an acceptable trade-off when sources have heterogeneous structures. **Accepted: heterogeneous signatures are by design.**
**Source:** GoF, Hickey (expert review 5). DDIA Ch.4 p.126. Reclassified 2026-04-06.
