# Technical Risk Register

**Date:** 2026-03-17 (updated 2026-05-03)
**Source:** Multi-expert engineering review, repo assimilation, falsification audits, expert code review (Martin, GoF, Feathers, Nygard, Kleppmann, Ousterhout, Hickey, Beck), magic-values compliance audit, stale-zarr incident 2026-04-24, pipeline verification audit 2026-04-30, ACLED integration test review 2026-05-02, ACLED test review 2026-05-03, ACLED compilation test review 2026-05-05
**Status:** 154 concern IDs assigned (C-28 merged into C-31, C-107 merged into C-60): 104 resolved, 42 open/deferred (12 resolved awaiting archive move, 2 with fired triggers accepted at v1.0), 6 accepted by design. 22 disagreements: 22 resolved.
**Archive:** Resolved concerns and disagreements are in `archive/technical_risk_register_resolved.md`.

**Ranking criteria:** Impact if wrong x likelihood x detectability. Items marked **[DEFER]** are accepted risks or wait for a specific trigger condition. See ADR-020 for governance rationale.

---

## Open Items Summary

| ID | Tier | Title | Trigger | Package |
|----|------|-------|---------|---------|
| C-88 | 2 | SSH not restricted to PRIO/Uppsala IPs | Before production deployment | Server hardening |
| C-121 | 4 | Phase 6.4 documented but unexecuted (lessons from C-87) | Before executing Phase 6.4 | Server hardening |
| C-21 | 3 | No characterization tests for migration | Next migration batch planned | — |
| C-36 | 4 | UCDP API contract has no schema versioning | UCDP announces API v2 | UCDP schema |
| C-37 | 4 | `date_prec=5` semantics hardcoded | UCDP publishes codebook | UCDP schema |
| C-45 | 4 | No Parquet schema evolution strategy | UCDP removes/renames a field | UCDP schema |
| ~~C-31~~ | ~~4~~ | ~~Candidate source depends on annual source (incl. C-28)~~ | Resolved 2026-04-27 | Code cleanup |
| C-44 | 4 | Harvest pipeline template is implicit — trigger fired, accepted at v1.0 | 5 sources exist | V-Dem readiness |
| C-46 | 4 | No ledger write idempotency | External systems consume ledger | — |
| C-32 | — | Source registry returns `Any` | Accepted by design | — |
| C-29 | 4 | No end-to-end integration test — trigger fired, accepted at v1.0 | Server in production | Test infra |
| C-70 | 4 | No circuit breaker for UCDP API | Multi-operator deployment | UCDP resilience |
| C-72 | 4 | HTTP 429 not distinguished from 500 | UCDP returns 429s | UCDP resilience |
| C-74 | 4 | CompilationConfig leaks strategy vocabulary | User confusion observed | — |
| C-75 | 4 | FeatureFrame shallow abstraction | Recurring misuse patterns | — |
| C-78 | 4 | `_place_events_columnar` hard to test in isolation | Compilation tests exceed 5s | Test infra |
| C-79 | 4 | Compilation/consolidation require real Parquet I/O | Test suite exceeds 30s | Test infra |
| C-03 | 4 | Protocol proliferation in synthetic module | 2nd implementation needed | — |
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
| ~~C-122~~ | ~~3~~ | ~~Consumer model has no runtime data fetch from Hetzner~~ | Resolved 2026-04-19 | Consumer integration |
| ~~C-123~~ | ~~4~~ | ~~`africa_me_legacy` region file not distributed~~ | Resolved 2026-04-19 | Consumer integration |
| ~~C-124~~ | ~~4~~ | ~~No consumer onboarding for remote zarr credentials~~ | Resolved 2026-04-19 | Consumer integration |
| C-10 | — | Ontology vocabulary overhead | Accepted | — |
| C-38 | — | Version string year offset assumes 21st century | Never (2099) | — |
| C-41 | — | Digest truncation collision risk | Records exceed 100M | — |
| C-06 | — | Provenance composability | Deferred by design | — |
| C-07 | — | Frozen dataclass pattern repeated | Deferred by design | — |

## Work Packages

Items that should be resolved together:

| Package | Items | Trigger |
|---------|-------|---------|
| **Server hardening** | C-88, C-121 (C-84, C-85, C-86, C-87 resolved) | Before production deployment |
| **V-Dem readiness** | C-44 (C-91 resolved) | Before V-Dem integration |
| **UCDP API resilience** | C-70, C-72 | Multi-operator deployment |
| **UCDP schema defense** | C-36, C-37, C-45 | UCDP API change |
| **Test infrastructure** | C-29, C-78, C-79, C-146 | Test suite growth (C-60 resolved) |
| **Code cleanup** | ~~C-31~~, C-93 | Next refactor opportunity (C-80, C-112, C-31 resolved) |
| ~~**Consumer integration**~~ | ~~C-122, C-123, C-124~~ | ~~Resolved~~ |
| ~~**Query correctness**~~ | ~~C-127~~ | Resolved 2026-04-27: warning on fallback, export already writes feature_order |
| **ADR-003 compliance** | ~~C-128~~, C-129 | Before next assembly/compilation change (C-128 resolved) |
| **Operational monitoring** | C-131, C-132, C-136, C-147 | Before relying on Hetzner pipeline without manual checks |
| **Scaling headroom** | C-144, C-145 | Before consolidated store exceeds ~5M rows |
| **Data integrity** | C-137, C-138, C-139, C-149 | Before relying on served data for model training |
| **Data boundary** | C-130, C-133, ~~C-134~~, C-135 | Before consumer models train on data from the factory (C-134 resolved) |
| ~~**Test coverage**~~ | ~~C-140, C-141, C-142, C-143~~ | Resolved 2026-04-26: 32 tests added |
| ~~**ACLED test coverage**~~ | ~~C-150, C-151, C-152~~ | Resolved 2026-05-02: 13 Red tests + 5 profile tests + 3 CICs added |
| **Migration scope** | ~~C-125~~, C-126 | Before claiming full viewser replacement for the fleet |

---

## Tier 1 — Fix Immediately

---

## Tier 2 — Fix Before Sharing Server Access

### C-88: SSH not restricted to PRIO/Uppsala IPs — [DEFER]
SSH is open to all source IPs. IT head advised whitelisting PRIO and Uppsala VPN IPs via fail2ban or Hetzner firewall, requiring VPN for SSH access. **Trigger: configure before production deployment.** Procedure documented in `hetzner_deployment_guide.md` Phase 6.4. Requires PRIO/Uppsala VPN CIDR ranges from IT.
**Source:** PRIO IT security guidance, server setup 2026-03-28

### ~~C-128: Scripts infer grid shape from arrays without config validation~~ — RESOLVED
**Resolved 2026-04-27.** Swapped validation/unpacking order in `assemble_grid.py` and `export_dataframe.py` so `assert_grid_shape()` runs before `.shape` unpacking, matching `compile_grid.py` which was already correct. Added 3 structural regression tests in `test_scripts.py::TestGridValidationOrder`.
**Source:** Magic-values compliance audit 2026-04-21. Cross-ref: ADR-003 (forbidden inference patterns).

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

### ~~C-150: Zero Red team tests for ACLED pipeline~~ — RESOLVED
**Resolved 2026-05-02.** Added `TestFetchAcledRed` (5 tests), `TestConsolidateAcledRed` (4 tests), `TestBuildAcledV1Red` (4 tests) covering: token endpoint garbage, missing `expires_in` fallback, non-list API data, missing required fields, frozen mutation, malformed filenames, corrupted Parquet, schema drift, malformed event dates, total filter elimination, missing store columns.
**Source:** ACLED integration test review (2026-05-02). Cross-ref: C-72 (HTTP 429 not distinguished), C-45 (no schema evolution strategy).

### ~~C-127: Zarr backend returns features in different order than npy backend~~ — RESOLVED
**Resolved 2026-04-27.** `_load_grid_from_zarr()` now emits `UserWarning` when falling back to `sorted(data_vars)` due to missing `feature_order` attr. `export_zarr.py` already writes `feature_order` (since 2026-04-21). Together these close the silent divergence: new exports are correct, old stores warn. Added 2 tests in `test_query.py::TestZarrFeatureOrderFallback`.
**Source:** Verification examples suite (M13), 2026-04-21. Cross-ref: C-117 (zarr spatial subsetting).

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

### ~~C-140: v1.2.6/v1.2.7 incident fixes have zero test coverage~~ — RESOLVED
**Resolved 2026-04-26.** Added 7 tests: `TestTotalCountAssertionBeige` (4 tests: tolerance pass, truncation raises, exact boundary, max_pages skip) and `TestRateLimitBackoffRed` (3 tests: HTTP 400 retry with backoff, exhaustion raises, non-400 bypass). Also added `TestValidateEnvelopeRed` (3 tests) and `TestUcdpAnnualRegistration` (1 test).
**Source:** Test review 2026-04-26. Cross-ref: C-137, C-138, C-139 (data integrity).

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

### ~~C-134: `get_last_valid_month_id()` silently returns None on all errors~~ — RESOLVED
**Resolved 2026-04-27.** Replaced broad `except Exception` with specific `except (URLError, HTTPError, TimeoutError)` that logs at ERROR and re-raises. `json.loads` moved outside the try-except so `JSONDecodeError` propagates naturally. `None` now only returned when the zarr store legitimately lacks the attribute. Added 4 tests: `test_raises_on_network_error`, `test_raises_on_auth_failure`, `test_raises_on_json_parse_error`, `test_logs_error_on_network_failure`.
**Source:** Tech-debt-cleanup audit (2026-04-22). Cross-ref: C-130 (zero-padding metadata).

### ~~C-141: UCDP config class validation partially untested~~ — RESOLVED
**Resolved 2026-04-26.** Added 8 Beige tests across three config classes: `UcdpAnnualConfig` (page_delay, timeout), `UcdpCandidateConfig` (page_size, max_retries, timeout), `UcdpDot9Config` (page_size, max_retries, timeout). All CIC-guaranteed fail-loud branches now tested.
**Source:** Test review 2026-04-26. Cross-ref: C-31, C-07.

### ~~C-142: datafactory_query consumer entry point has zero Red/Beige tests~~ — RESOLVED
**Resolved 2026-04-26.** Added `TestLoadDatasetBeige` (2 tests: single-feature request, explicit-matches-default) and `TestLoadDatasetRed` (5 tests: corrupted grid, mismatched feature count, mismatched pgids shape, NaN-filled grid, zero time steps).
**Source:** Test review 2026-04-26. Cross-ref: C-127, C-130.

### C-21: No characterization tests for migration source — [DEFER]
The metric lab code being migrated has its own tests, but this repo has no "golden output" tests that capture expected behavior of migrated code. Migration without characterization tests risks silent behavioral divergence. **Trigger: when next migration batch is planned.**
**Source:** Feathers
**Update 2026-04-21:** Partially addressed by M13 (verification examples suite). 15 `examples/ex_*.py` scripts verify consumer-facing API contracts end-to-end. Not full characterization tests, but covers the consumer surface model developers depend on.

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

See also C-78 (`_place_events_columnar` testability).

### C-145: Viewpoint builder loads full consolidated store into memory — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-145 |
| Tier | 3 |
| Source | repo-assimilation (2026-04-30) |
| Trigger | When the consolidated store exceeds ~5M rows on a memory-constrained machine, or when building viewpoints on developer laptops with <16GB RAM |
| Location | `src/datafactory_viewpoint/builders/ucdp_v1.py:129` (`pq.read_table(config.consolidated_path)`) |

`build_ucdp_v1` calls `pq.read_table()` which materializes the entire consolidated Parquet store as a PyArrow Table. The table is then sorted by `id` (creating a second copy), and iterated as groups of Python dicts. The docstring notes peak memory was reduced from ~4GB to ~1GB via streaming output columns, but the initial `pq.read_table` plus the sorted copy still dominate. At ~2.3M events with ~45 columns this is manageable on the 32GB server. A future migration to row-group streaming or predicate pushdown would decouple viewpoint memory from store size.

See also C-79 (Parquet I/O in tests).

### C-146: Assembly logic lives in script, not importable package — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-146 |
| Tier | 3 |
| Source | repo-assimilation (2026-04-30) |
| Trigger | When assembly orchestration needs refactoring, or a second assembly path is needed (e.g., different feature sets for different consumers) |
| Location | `scripts/assemble_grid.py` (~350 LOC procedural, not in any `src/datafactory_*` package) |

Every other layer exposes its core logic as an importable function: `consolidate_ucdp()`, `build_ucdp_v1()`, `compile_grid()`, `load_dataset()`. Assembly is the exception — its spatial join, static feature broadcast, and admin boundary merge logic lives entirely in `assemble_grid.py`'s `main()`. `test_assemble.py` tests sub-components (spatial join helper, GID lookup) but cannot import and test the orchestration function directly. Extracting an `assemble_grid()` function into `datafactory_compilation` or a new `datafactory_assembly` package would make the logic importable and directly testable.

See also C-29 (no end-to-end integration test).

### ~~C-151: No CICs for ACLED config classes~~ — RESOLVED
**Resolved 2026-05-02.** Created `docs/CICs/AcledConfig.md`, `docs/CICs/AcledConsolidationConfig.md`, `docs/CICs/AcledViewpointConfig.md` following the 11-section template. Frozen-enforcement tests added for all three configs.
**Source:** ACLED integration test review (2026-05-02). Cross-ref: C-07 (frozen dataclass pattern repeated), C-150 (zero Red tests).

### ~~C-152: ACLED profiles and `list_acled_profiles()` untested~~ — RESOLVED
**Resolved 2026-05-02.** Added `TestAcledProfilesGreen` (4 tests: `load_acled_violence_only`, `load_acled_all_events`, `load_with_override`, `list_acled_profiles`) and `TestAcledProfilesRed` (1 test: `unknown_acled_profile_raises`) in `tests/test_acled_viewpoint.py`.
**Source:** ACLED integration test review (2026-05-02). Cross-ref: C-150 (ACLED test gaps).

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

### ~~C-31: Candidate source depends on annual source~~ — RESOLVED
**Resolved 2026-04-27.** Extracted `_ucdp_common.py` with `ENVELOPE_KEYS`, `UCDP_GED_API_BASE`, and `validate_envelope()`. Candidate and .9 now import shared symbols from `_ucdp_common` instead of `ucdp_annual`. Discovery functions call `validate_envelope()` and use `data["TotalCount"]` instead of `.get("TotalCount", 0)`. Network try-except narrowed to only `requests.RequestException` so envelope validation errors propagate (ADR-008). Added 2 envelope rejection tests.
**Source:** Martin (expert review 5), falsification audit DoD005, magic-values audit 2026-04-21.

### C-44: Harvest pipeline template is implicit — [DEFER]
All five harvesters follow config->fetch->validate->compare->archive->store->provenance but no shared template enforces step order. A new source author must read existing sources to discover the pattern. **Trigger: extract `HarvestPipeline` when a 4th source is added.**
**Note (2026-04-04):** Trigger condition met — 5 sources exist (ucdp_annual, ucdp_candidate, ucdp_dot9, priogrid_static, gaul_admin). Accepted at v1.0 scope: all 5 harvesters work correctly, implicit template hasn't caused bugs. Reassess before V-Dem (6th source).
**Note (2026-05-02):** 6th source added (ACLED). Pattern was replicated from existing harvesters without issues. Template extraction deferred to V-Dem (7th source) or next refactor.
**Source:** GoF (expert review 6)

### C-46: No ledger write idempotency — [DEFER]
`append_ledger_entry()` has no dedup key. Process crash after append but before caller return causes duplicate on retry. Ledger readers tolerate duplicates. Kleppmann (Ch.12 pp.516-518) argues exactly-once semantics require idempotence via operation identifiers — each write carries a unique ID; consumers deduplicate on read. Ch.7 p.231 warns that retrying a successful-but-unacknowledged write without dedup causes silent duplication. Recommended approach: add an `operation_id` field (e.g., content digest of the entry) to each ledger record. **Trigger: consider when ledger is consumed by external systems requiring exactly-once semantics.**
**Source:** Kleppmann (expert review 6). DDIA Ch.7 p.231, Ch.12 pp.516-518.

### C-29: No end-to-end integration test — [DEFER]
Partially addressed by `test_integration.py` (100 events, realistic pipeline). Full-scale end-to-end with all 3 sources untested. **Trigger: add before production deployment.**
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
Callers must know magic strings (`"count"`, `"sum_field"`, `"max_field"`) and filter dict syntax. No IDE discoverability. **Trigger: consider enum-based strategy names if user confusion is observed.**
**Note (2026-04-08):** Renamed from `sum_best`/`max_best` to `sum_field`/`max_field` to reflect configurable `value_field`. Old names registered as backward-compatible aliases.
**Source:** Ousterhout (expert review #4)

### C-75: FeatureFrame is shallow — adds validation but little abstraction — [DEFER]
8 public methods/properties wrapping numpy arrays. Each method is 1-5 lines. Callers must understand `[N, D]` vs `[N, D, S]` shapes. Acceptable for a data wrapper; monitor if callers misuse. **Trigger: deepen if recurring misuse patterns emerge.**
**Source:** Ousterhout (expert review #4)

### C-78: `_place_events_columnar` hard to test in isolation — [DEFER]
100 lines of columnar bin-assignment logic tested only indirectly through `compile_grid()`. Core algorithm (lat/lon -> pgid, date -> month_index) could be extracted into a pure function. **Trigger: extract `compute_bin_assignments()` when compilation tests exceed 5 seconds.**
**Source:** Feathers (expert review #4)

### C-79: Compilation/consolidation require real Parquet I/O in tests — [DEFER]
`compile_grid()` and `consolidate_ucdp()` always read from disk. No seam to inject mock reader. Tests create actual Parquet files. **Trigger: add `read_table_fn` parameter when test suite exceeds 30 seconds.**
**Source:** Feathers (expert review #4)

### C-03: Protocol proliferation risk in synthetic module — [DEFER]
`src/datafactory_synthetic/ARCHITECTURE.md` plans 3 Protocols before any concrete implementation. Premature abstraction. **Trigger: defer Protocols until a second implementation is needed.**
**Source:** GoF, Hickey


### ~~C-143: request_with_retry has no Red tests~~ — RESOLVED
**Resolved 2026-04-26.** Added `TestRequestWithRetryRed` (2 tests: `requests.Timeout` retried, `HTTPError` with `response=None` retried not treated as 4xx).
**Source:** Test review 2026-04-26. Cross-ref: C-70, C-72.

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


### ~~C-125: No country-month (cm) aggregation — 48/70 models cannot migrate~~ — [RESOLVED]
Resolved 2026-04-21. `load_dataset(output_format="country_month")` now aggregates grid cells by country per month using `gaul0_code` as the grouping key. Adapter: `grid_to_country_month()` in `datafactory_adapters`. Active conflict features (ged_sb/ns/os_best) summed per (month_id, country_id). WDI/V-DEM/topic features remain out of scope (C-126 covers the transform gap).
**Source:** Falsification audit 2026-04-20 (F3). Cross-ref: S1 in `test_falsification_viewser_replacement.py`.

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
### C-109: Advisory file locks (fcntl) don't work across NFS — [DEFER]
`file_lock()` in `digests_and_ledgers.py` uses `fcntl.flock` which is advisory and may not work on network filesystems (NFS, CIFS). Currently deployed on local SSD on the Hetzner server. A migration to shared/network storage would silently break concurrency protection for ledger writes. Kleppmann (Ch.7 pp.234-236) describes read-committed isolation via locks — our fcntl.flock achieves this at the file level on local disk. Ch.8 pp.301-303 introduces fencing tokens as a safety mechanism when locks can be stale: a monotonically increasing token ensures an expired lock holder cannot perform writes. This pattern would be needed if we migrate to network storage. **Trigger: verify lock behavior before migrating to network-attached storage or multi-server deployment.**
**Source:** Repo assimilation 2026-04-04 (Phase 5, invariant 10). DDIA Ch.7 pp.234-236, Ch.8 pp.301-303.

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
