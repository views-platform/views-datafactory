# Technical Risk Register

**Date:** 2026-03-17 (updated 2026-04-21)
**Source:** Multi-expert engineering review, repo assimilation, falsification audits, expert code review (Martin, GoF, Feathers, Nygard, Kleppmann, Ousterhout, Hickey, Beck), magic-values compliance audit
**Status:** 129 concern IDs assigned (C-28 merged into C-31, C-107 merged into C-60): 92 resolved, 29 open/deferred (2 with fired triggers accepted at v1.0), 6 accepted by design. 22 disagreements: 22 resolved.
**Archive:** Resolved concerns and disagreements are in `technical_risk_register_resolved.md`.

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
| C-31 | 4 | Candidate source depends on annual source (incl. C-28) | 3rd shared function needed | Code cleanup |
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
| C-128 | 2 | Scripts infer grid shape without config validation (ADR-003 forbidden) | Compilation produces unexpected spatial dims | ADR-003 compliance |
| C-127 | 2 | Zarr backend returns features in alphabetical order, npy preserves feature_names.json order | Consumer switches from npy to zarr backend | Query correctness |
| C-129 | 3 | Partition boundaries (month IDs) have no single source of truth | VIEWS shifts partition boundaries | ADR-003 compliance |
| C-125 | 3 | No cm aggregation — 48/70 models cannot migrate | First cm model attempts datafactory migration | Migration scope |
| C-126 | 3 | No transform layer — 14 viewser transforms not replaceable | Model migration requires derived features | Migration scope |
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
| **Test infrastructure** | C-29, C-78, C-79 | Test suite growth (C-60 resolved) |
| **Code cleanup** | C-31, C-93 | Next refactor opportunity (C-80, C-112 resolved) |
| **Consumer integration** | C-122, C-123, C-124 | Before bright_starship can be used by anyone other than the developer |
| **Query correctness** | C-127 | Before consumer switches from npy to zarr backend |
| **ADR-003 compliance** | C-128, C-129 | Before next assembly/compilation change |
| **Migration scope** | C-125, C-126 | Before claiming full viewser replacement for the fleet |

---

## Tier 1 — Fix Immediately

---

## Tier 2 — Fix Before Sharing Server Access

### C-88: SSH not restricted to PRIO/Uppsala IPs — [DEFER]
SSH is open to all source IPs. IT head advised whitelisting PRIO and Uppsala VPN IPs via fail2ban or Hetzner firewall, requiring VPN for SSH access. **Trigger: configure before production deployment.** Procedure documented in `hetzner_deployment_guide.md` Phase 6.4. Requires PRIO/Uppsala VPN CIDR ranges from IT.
**Source:** PRIO IT security guidance, server setup 2026-03-28

### C-128: Scripts infer grid shape from arrays without config validation
`assemble_grid.py:107` unpacks `n_t, n_h, n_w, n_ucdp = ucdp_grid.shape` and uses the inferred `n_h`, `n_w` for all subsequent operations (row/col loops, gid lookups) without asserting they match `GridConfig`. Same pattern in `export_dataframe.py:102`. ADR-003 explicitly lists "inferring grid resolution from the shape of a compiled npy array" as a **forbidden** inference pattern. A corrupted or mis-assembled npy (wrong spatial dimensions) would silently produce wrong output — incorrect gid→cell mappings, wrong feature assignments — with no error signal.

**Trigger:** Compilation bug or manual assembly produces a grid with unexpected spatial dimensions (e.g., 180x360 from a half-resolution run).
**Location:** `scripts/assemble_grid.py:107`, `scripts/export_dataframe.py:102`, `scripts/compile_grid.py:160-163`, `scripts/presentation_plots.py:174,231,293`.
**Resolution:** Add `assert n_h == DEFAULT_GRID_CONFIG.nrow` and `assert n_w == DEFAULT_GRID_CONFIG.ncol` after shape unpacking in all affected scripts.
**Source:** Magic-values compliance audit 2026-04-21. Cross-ref: ADR-003 (forbidden inference patterns).

### C-127: Zarr backend returns features in different order than npy backend
The zarr loader in `dataset.py:154-157` falls back to `sorted(ds.data_vars)` (alphabetical) when the zarr store lacks a `feature_order` attr. The npy loader (`dataset.py:215`) reads `feature_names.json`, which preserves the compilation-time order. A consumer using FeatureFrame and indexing `y_features` by column position (e.g., `ff.y_features[:, 0]`) will silently get different features depending on which backend is used. The current zarr store at `data/assembled/grid.zarr` has no `feature_order` attr. **This is silent data divergence with no error signal.**

**Trigger:** Consumer switches from local npy to zarr backend (local or remote) and uses positional indexing on FeatureFrame.
**Location:** `src/datafactory_query/dataset.py:154-157` (zarr fallback), `src/datafactory_query/dataset.py:215` (npy path). Zarr store at `data/assembled/grid.zarr` (missing attr).
**Resolution:** Either (a) write `feature_order` attr during zarr export (`scripts/export_zarr.py`), or (b) reorder zarr output to match `features` parameter order in `_load_grid_from_zarr`, or (c) both.
**Source:** Verification examples suite (M13), `ex_zarr_local.py` discovered column order mismatch during TDD, 2026-04-21. Cross-ref: C-117 (zarr spatial subsetting).

---

## Tier 3 — Improve Quality

### C-129: Partition boundaries (month IDs) have no single source of truth
The calibration/validation/forecasting partition boundaries (121/444, 445/492, 493/540) appear as bare literals in 4+ independent locations: `scripts/generate_consumer_data.py:56` (`PARTITIONS` dict), `examples/ex_partitions.py` (6+ occurrences in assertions), `tests/test_consumer_data.py:162,169`, and downstream in `bright_starship/configs/config_partitions.py`. No shared authoritative definition exists. Adding a new partition type or shifting a boundary (e.g., extending calibration) requires coordinated find-and-replace across repos with no compiler or test to catch a missed update. Per ADR-003: "a single source of truth must be designated."

**Trigger:** VIEWS operational calendar shifts partition boundaries (e.g., extending calibration end from month 444 to 456).
**Location:** `scripts/generate_consumer_data.py:56`, `examples/ex_partitions.py:21-101`, `tests/test_consumer_data.py:162,169`, `tests/test_consumer_parity.py:57`, downstream `bright_starship/configs/config_partitions.py`.
**Resolution:** Define a `PARTITIONS` frozen dict or dataclass in a shared location within `src/` and have all consumers import from it.
**Source:** Magic-values compliance audit 2026-04-21. Cross-ref: ADR-003 (single source of truth).

### C-21: No characterization tests for migration source — [DEFER]
The metric lab code being migrated has its own tests, but this repo has no "golden output" tests that capture expected behavior of migrated code. Migration without characterization tests risks silent behavioral divergence. **Trigger: when next migration batch is planned.**
**Source:** Feathers
**Update 2026-04-21:** Partially addressed by M13 (verification examples suite). 15 `examples/ex_*.py` scripts verify consumer-facing API contracts end-to-end. Not full characterization tests, but covers the consumer surface model developers depend on.

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

### C-31: Candidate source depends on annual source — [DEFER]
`ucdp_candidate.py` imports 4 symbols and `ucdp_dot9.py` imports 5 symbols from `ucdp_annual.py` (including `UcdpAnnualConfig`, `fetch_paginated`, `FIELD_TYPES`, `REQUIRED_FIELDS`, and `get_ucdp_token`). Changing annual's API client could break candidate. Additionally, `ucdp_candidate.py:188-198` constructs `UcdpAnnualConfig(start_year=2000, end_year=2099)` to reuse `fetch_paginated` — sends unnecessary 100-year date range (works correctly but is a workaround). **Trigger: extract `_ucdp_common.py` when a 3rd shared function is needed. Resolution also addresses former C-28.**
**Source:** Martin (expert review 5), falsification audit DoD005
**Update 2026-04-21:** Magic-values audit found the UCDP API base URL `"https://ucdpapi.pcr.uu.se/api/gedevents"` hardcoded identically in all 3 config classes (`ucdp_annual.py:94`, `ucdp_candidate.py:86`, `ucdp_dot9.py:90`). This is a specific ADR-003 violation (no single source of truth) and a symptom of the same coupling. Extracting `_ucdp_common.py` would also centralize this URL.

### C-44: Harvest pipeline template is implicit — [DEFER]
All five harvesters follow config->fetch->validate->compare->archive->store->provenance but no shared template enforces step order. A new source author must read existing sources to discover the pattern. **Trigger: extract `HarvestPipeline` when a 4th source is added.**
**Note (2026-04-04):** Trigger condition met — 5 sources exist (ucdp_annual, ucdp_candidate, ucdp_dot9, priogrid_static, gaul_admin). Accepted at v1.0 scope: all 5 harvesters work correctly, implicit template hasn't caused bugs. Reassess before V-Dem (6th source).
**Source:** GoF (expert review 6)

### C-46: No ledger write idempotency — [DEFER]
`append_ledger_entry()` has no dedup key. Process crash after append but before caller return causes duplicate on retry. Ledger readers tolerate duplicates. Kleppmann (Ch.12 pp.516-518) argues exactly-once semantics require idempotence via operation identifiers — each write carries a unique ID; consumers deduplicate on read. Ch.7 p.231 warns that retrying a successful-but-unacknowledged write without dedup causes silent duplication. Recommended approach: add an `operation_id` field (e.g., content digest of the entry) to each ledger record. **Trigger: consider when ledger is consumed by external systems requiring exactly-once semantics.**
**Source:** Kleppmann (expert review 6). DDIA Ch.7 p.231, Ch.12 pp.516-518.

### C-29: No end-to-end integration test — [DEFER]
Partially addressed by `test_integration.py` (100 events, realistic pipeline). Full-scale end-to-end with all 3 sources untested. **Trigger: add before production deployment.**
**Note (2026-04-04):** Trigger condition met — server in production at 204.168.219.108. Accepted at v1.0 scope: integration test covers the critical harvest→compile path, `verify_remote.py` validates the deployed output (10/10 checks). Reassess before V-Dem.
**Source:** Repo assimilation, Feathers

### C-70: No circuit breaker for UCDP API — [DEFER]
After `max_retries` exhaustion, harvest fails immediately. If UCDP API is down for hours, every harvest attempt exhausts retries. No "open circuit" to fail fast on known-dead endpoints. Kleppmann (Ch.7 p.231) warns that retrying overload "will make the problem worse, not better" and recommends exponential backoff with distinct handling for overload vs transient errors. Ch.8 pp.281-283 discusses timeout-based fault detection and network congestion amplification. **Trigger: implement before multi-operator or automated deployment.**
**Source:** Nygard (expert review #4). DDIA Ch.7 p.231, Ch.8 pp.281-283.

### C-72: HTTP 429 not distinguished from 500 — [DEFER]
Rate-limit responses get the same retry treatment as server errors. No `Retry-After` header parsing. Kleppmann (Ch.7 p.231) explicitly argues "it is only worth retrying after transient errors (e.g., deadlock, network interruption); after a permanent error, a retry would be pointless" and that overload errors need distinct handling. Ch.8 p.281 notes short timeouts risk declaring healthy services dead during load spikes. **Trigger: if UCDP starts returning 429s (not observed to date).**
**Source:** Nygard (expert review #4). DDIA Ch.7 p.231, Ch.8 p.281.

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


### C-125: No country-month (cm) aggregation — 48/70 models cannot migrate — [DEFER]
`load_dataset()` returns data indexed on `(month_id, priogrid_gid)` only. 48 of 70 VIEWS models use `country_month` level of analysis, requiring grid-to-country aggregation that the factory does not provide. These models remain dependent on viewser until a cm aggregation layer exists — either in datafactory, in a separate feature-engineering repo, or in the model classes themselves. The factory's scope is data access, not feature engineering; this is a known boundary, not an omission. **Trigger: first cm model attempts migration from viewser to datafactory.**
**Source:** Falsification audit 2026-04-20 (F3). Cross-ref: S1 in `test_falsification_viewser_replacement.py`.

### C-126: No transform layer — models using viewser transforms cannot migrate — [DEFER]
14 distinct viewser transforms are in active use across the fleet: `replace_na`, `fill`, `tlag` (832 uses), `countrylag` (486), `gte` (316), `decay` (288), `time_since` (285), `ln` (233), `moving_sum`, `spatial.lag`, `sptime_dist`, `treelag`, `delta`, `moving_average`. The factory provides raw values + `fillna(0)` only. Models using any transform beyond fillna cannot migrate without reimplementing those transforms outside viewser. The transform layer will likely be a separate repo or integrated into model classes (hydranet, r2darts2, stepshifter) — too early to decide architecture. **Trigger: model migration plan requires features derived from viewser transforms.**
**Source:** Falsification audit 2026-04-20 (F7). Cross-ref: S2 in `test_falsification_viewser_replacement.py`.

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
