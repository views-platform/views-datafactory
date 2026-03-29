# Technical Risk Register

**Date:** 2026-03-17 (updated 2026-03-28)
**Source:** Multi-expert engineering review, repo assimilation, falsification audits, expert code review (Martin, GoF, Feathers, Nygard, Kleppmann, Ousterhout, Hickey, Beck)
**Status:** 69 concerns total: 38 resolved, 31 open/deferred. 17 disagreements: 17 resolved.
**Archive:** Resolved concerns and disagreements are in `technical_risk_register_resolved.md`.

**Ranking criteria:** Impact if wrong x likelihood x detectability. Items marked **[DEFER]** are accepted risks or wait for a specific trigger condition. See ADR-020 for governance rationale.

---

## Open Items Summary

| ID | Tier | Title | Trigger |
|----|------|-------|---------|
| D-03 | 1 | Fail-loud vs. operational resilience | Before production deployment |
| C-84 | 2 | Server runs everything as root | Before granting second user access |
| C-85 | 2 | Personal GitHub SSH key on shared server | Before granting second user access |
| C-86 | 2 | No deploy key — repo access tied to personal account | Before granting second user access |
| C-87 | 2 | No named user accounts on server | Before granting second user access |
| C-88 | 2 | SSH not restricted to PRIO/Uppsala IPs | Before production deployment |
| C-82 | 3 | ~~No GAUL retry integration test~~ | RESOLVED — `test_gaul_admin.py` |
| C-21 | 3 | No characterization tests for migration | Next migration batch planned |
| C-37 | 4 | `date_prec=5` semantics hardcoded | UCDP publishes codebook or change observed |
| C-36 | 4 | UCDP API contract has no schema versioning | UCDP announces API v2 |
| C-45 | 4 | No Parquet schema evolution strategy | UCDP removes/renames a field |
| C-31 | 4 | Candidate source depends on annual source | 3rd shared function needed |
| C-44 | 4 | Harvest pipeline template is implicit | 4th data source added |
| C-46 | 4 | No ledger write idempotency | External systems consume ledger |
| C-32 | 4 | Source registry returns `Any` | Type errors in consumer code |
| C-30 | 4 | No performance test for full-scale compilation | Before CI/CD pipeline |
| C-29 | 4 | No end-to-end integration test | Before production deployment |
| C-28 | 4 | Candidate uses fake annual config workaround | Extract `_ucdp_common.py` (C-31) |
| C-27 | 4 | ~~Retry pattern duplicated in 3 modules~~ | RESOLVED — extracted to `datafactory_http` |
| C-41 | 4 | Digest truncation collision risk | Records exceed 100M |
| C-38 | 4 | Version string year offset assumes 21st century | Never (2099) |
| C-10 | 4 | Ontology vocabulary overhead | Accepted |
| C-70 | 4 | No circuit breaker for UCDP API | Multi-operator deployment |
| C-71 | 4 | ~~No retry jitter~~ | RESOLVED — `random.uniform(0, 1)` added |
| C-72 | 4 | HTTP 429 not distinguished from 500 | UCDP returns 429s |
| C-74 | 4 | CompilationConfig leaks strategy vocabulary | User confusion observed |
| C-75 | 4 | FeatureFrame shallow abstraction | Recurring misuse patterns |
| C-77 | — | ~~Ledger archive retention unbounded~~ | RESOLVED — 9-archive cap is the retention policy |
| C-78 | 4 | `_place_events_columnar` hard to test in isolation | Compilation tests exceed 5s |
| C-79 | 4 | Compilation/consolidation require real Parquet I/O | Test suite exceeds 30s |
| C-80 | 4 | Registry boilerplate duplicated 5x | 6th registry added |
| C-03 | 4 | Protocol proliferation in synthetic module | 2nd implementation needed |
| C-60 | 4 | Health check output not tested with mock ledgers | check_health.py modified |
| C-61 | 4 | No schema evolution test | 3rd data source |
| C-81 | 4 | ~~GAUL shapefile download has no retry logic~~ | RESOLVED — uses `request_with_retry` |
| C-83 | 4 | ~~Retry retries on 4xx client errors~~ | RESOLVED — 4xx fail-fast, 5xx retry |
| C-06 | — | Provenance composability | Deferred by design |
| C-07 | — | Frozen dataclass pattern repeated | Deferred by design |

---

## Tier 1 — Fix Before Production

### D-03: Fail-loud vs. operational resilience
ADR-003/008 mandate fail-loud everywhere. Nygard asks what the operational experience is when the UCDP API is down for 3 days. For a production forecasting system, some resilience policy is needed. **Policy defined in ADR-018 (operator-mediated bounded staleness). Code-level implementation partially complete (2026-03-28):**
- `harvest_ucdp.py` now exits non-zero on harvest failure (was always exiting 0)
- `refresh_pipeline.sh` has ERR trap: writes `logs/pipeline_failure.json` sentinel on failure, optionally sends email if `ALERT_EMAIL` is set
- `check_health.py` reports staleness and failures (already existed)
**Remaining gap:** No freshness indicator in zarr/parquet exports for consumers. **Trigger: add before second consumer.**
**Source:** Nygard (expert reviews 4, 6, 7)

---

## Tier 2 — Fix Before Sharing Server Access

### C-84: Server runs everything as root — [DEFER]
All pipeline operations, git, and Caddy configuration run as `root` on the Hetzner server. No separation of privileges. A mistake as root can destroy the OS. IT head explicitly advised "limit who can sudo." **Trigger: create a non-root service account (e.g., `views-deploy`) before granting anyone else server access.**
**Source:** PRIO IT security guidance, server setup 2026-03-28

### C-85: Personal GitHub SSH key on shared server — [DEFER]
The server's SSH key (`/root/.ssh/id_ed25519`) is registered on Simon's personal GitHub account. If another user gets root access, they effectively have Simon's GitHub credentials for all repos. **Trigger: replace with a repo-scoped deploy key before granting second user access.**
**Source:** Server setup 2026-03-28

### C-86: No deploy key — repo access tied to personal account — [DEFER]
GitHub access from the server uses a personal SSH key, not a deploy key. Deploy keys are scoped to a single repo, are read-only by default, and don't grant access to other repos on the account. **Trigger: create a GitHub deploy key for `views-platform/views-datafactory` and remove the personal key from the server.**
**Source:** Server setup 2026-03-28

### C-87: No named user accounts on server — [DEFER]
Only `root` exists. IT head advised: named accounts per person, no shared accounts, plus a break-glass emergency account with securely stored credentials. **Trigger: create named accounts before granting second user access.**
**Source:** PRIO IT security guidance, server setup 2026-03-28

### C-88: SSH not restricted to PRIO/Uppsala IPs — [DEFER]
SSH is open to all source IPs. IT head advised whitelisting PRIO and Uppsala VPN IPs via fail2ban or Hetzner firewall, requiring VPN for SSH access. **Trigger: configure before production deployment.**
**Source:** PRIO IT security guidance, server setup 2026-03-28

---

## Tier 3 — Improve Quality

### C-82: ~~No GAUL retry integration test~~ RESOLVED
Added `test_gaul_admin.py` with `test_retries_on_transient_failure` (verifies `_download_shapefile_zip` retries via `request_with_retry`) and `test_skips_download_when_cached` (verifies cache-hit path).
**Source:** Feathers, Beck, Nygard (expert review #7)

### C-21: No characterization tests for migration source — [DEFER]
The metric lab code being migrated has its own tests, but this repo has no "golden output" tests that capture expected behavior of migrated code. Migration without characterization tests risks silent behavioral divergence. **Trigger: when next migration batch is planned.**
**Source:** Feathers

---

## Tier 4 — Accept or Defer

### C-37: `date_prec=5` semantics hardcoded — [DEFER]
`temporal_distribution.py:22` defines `_SUMMARY_DATE_PREC = 5`. If UCDP changes `date_prec` semantics, temporal distribution silently produces wrong results. No UCDP documentation exists for `date_prec` values. **Trigger: UCDP publishes a codebook or changes observed empirically.**
**Source:** Repo assimilation

### C-36: UCDP API contract has no schema versioning — [DEFER]
API envelope format and 13 `REQUIRED_FIELDS` are hardcoded in `ucdp_annual.py:43-72,176-190`. No schema version negotiation. Fail-loud catches field removals; field additions are harmless (silently preserved). **Trigger: UCDP announces API v2 or breaking change.**
**Source:** Repo assimilation

### C-45: No Parquet schema evolution strategy — [DEFER]
`pa.concat_tables(promote_options="default")` in `ucdp.py:439-441` silently adds columns when UCDP adds fields. Removed fields leave nulls in new records. No schema registry. **Trigger: UCDP removes a field or renames a column.**
**Source:** Kleppmann (expert review 6)

### C-31: Candidate source depends on annual source — [DEFER]
`ucdp_candidate.py:25-31` imports 5 symbols from `ucdp_annual.py` including `UcdpAnnualConfig`. Changing annual's API client could break candidate. **Trigger: extract `_ucdp_common.py` when a 3rd shared function is needed.**
**Source:** Martin (expert review 5)

### C-44: Harvest pipeline template is implicit — [DEFER]
All three UCDP harvesters follow config->fetch->validate->compare->archive->store->provenance but no shared template enforces step order. A 4th source author must read existing sources to discover the pattern. **Trigger: extract `HarvestPipeline` when a 4th source is added.**
**Source:** GoF (expert review 6)

### C-46: No ledger write idempotency — [DEFER]
`append_ledger_entry()` has no dedup key. Process crash after append but before caller return causes duplicate on retry. Ledger readers tolerate duplicates. **Trigger: consider when ledger is consumed by external systems requiring exactly-once semantics.**
**Source:** Kleppmann (expert review 6)

### C-32: Source registry returns `Any` — [DEFER]
`fetch_source` returns `Any` (widened from `Path` for candidate's `list[dict]`). Consumers can't rely on the return type. **Trigger: consider `SourceResult` union if type errors appear in consumer code.**
**Source:** GoF, Hickey (expert review 5)

### C-30: No performance test for full-scale compilation — [DEFER]
60-second target (NF-5: 259,200 cells x 432 months) has no test. Full-scale operation proven in practice (1.7M events, <60s). **Trigger: add performance test before CI/CD pipeline.**
**Source:** Repo assimilation, Nygard

### C-29: No end-to-end integration test — [DEFER]
Partially addressed by `test_integration.py` (100 events, realistic pipeline). Full-scale end-to-end with all 3 sources untested. **Trigger: add before production deployment.**
**Source:** Repo assimilation, Feathers

### C-28: Candidate source uses fake annual config workaround — [DEFER]
`ucdp_candidate.py:188-198` constructs `UcdpAnnualConfig(start_year=2000, end_year=2099)` to reuse `fetch_paginated`. Sends unnecessary 100-year date range. Works correctly. **Trigger: fix when extracting `_ucdp_common.py` (C-31).**
**Source:** Falsification audit DoD005

### C-27: ~~Retry pattern duplicated in 3 modules~~ RESOLVED
Extracted `request_with_retry` to new Layer 0 package `datafactory_http`. All callers (`ucdp_annual`, `ucdp_candidate`, `ucdp_dot9`, `shapefile_harvester`, `gaul_admin`) now import from the shared module.
**Source:** Repo assimilation, expert review 4, tech debt cleanup 2026-03-27

### C-41: Digest truncation collision risk — [DEFER]
`DIGEST_TRUNCATE = 16` hex chars = 64-bit space. 50% collision at ~4B items. Fine at ~2M events. **Trigger: consider when total records exceed 100M or digests are used as unique keys.**
**Source:** Repo assimilation

### C-38: Version string year offset assumes 21st century — [DEFER]
`_DOT9_YEAR_OFFSET = 2000` / `_CANDIDATE_YEAR_OFFSET = 2000` in `ucdp_dot9.py:50` and `ucdp_candidate.py:43`. Breaks silently for pre-2000 or post-2099 data. UCDP data starts 1989 (annual uses full version strings). **Trigger: never (2099 is 73 years away).**
**Source:** Repo assimilation

### C-10: Ontology vocabulary overhead — [DEFER]
Terms like "Source Nodes," "Compilation Edges," "Explicit Non-Entities" are precise but add conceptual overhead. For a 7-package project, governance is heavy. **Accepted: governance has proven itself (ADR-008 caught bugs in 3 audits). Cost is documentation maintenance, not development velocity.**
**Source:** Ousterhout

### C-70: No circuit breaker for UCDP API — [DEFER]
After `max_retries` exhaustion, harvest fails immediately. If UCDP API is down for hours, every harvest attempt exhausts retries. No "open circuit" to fail fast on known-dead endpoints. **Trigger: implement before multi-operator or automated deployment.**
**Source:** Nygard (expert review #4)

### C-71: ~~No retry jitter~~ RESOLVED
Added `random.uniform(0, 1)` jitter to exponential backoff in `datafactory_http/retry.py`. Delay is now `2^attempt + random(0, 1)` instead of fixed `2^attempt`.
**Source:** Nygard (expert review #4)

### C-72: HTTP 429 not distinguished from 500 — [DEFER]
Rate-limit responses get the same retry treatment as server errors. No `Retry-After` header parsing. **Trigger: if UCDP starts returning 429s (not observed to date).**
**Source:** Nygard (expert review #4)

### C-73: ~~Grid shape transposition produces silent wrong results~~ RESOLVED
Added shape validation (ndim + spatial dim match) to `_flatten_grid()`, `feature_frame_to_grid()`, and `FeatureFrame.from_grid()`. Transposed grids, 3D grids, and 1D pgids now raise `ValueError`. Retired `visualize_grid.py` (superseded scaffolding with live indexing bugs from an older grid convention).
**Source:** Ousterhout (expert review #4), failure mode analysis

### C-74: CompilationConfig leaks strategy vocabulary — [DEFER]
Callers must know magic strings (`"count"`, `"sum_best"`, `"max_best"`) and filter dict syntax. No IDE discoverability. **Trigger: consider enum-based strategy names if user confusion is observed.**
**Source:** Ousterhout (expert review #4)

### C-75: FeatureFrame is shallow — adds validation but little abstraction — [DEFER]
8 public methods/properties wrapping numpy arrays. Each method is 1-5 lines. Callers must understand `[N, D]` vs `[N, D, S]` shapes. Acceptable for a data wrapper; monitor if callers misuse. **Trigger: deepen if recurring misuse patterns emerge.**
**Source:** Ousterhout (expert review #4)

### C-76: ~~Falsification tests are skipped, not running~~ RESOLVED
Registered `falsification` pytest marker. 11 stubs now use `@pytest.mark.falsification()` instead of `@pytest.mark.skip()`. Auto-skipped by default; visible with `--run-falsification`. Normal `pytest` output shows 0 skipped.
**Source:** Beck (expert review #4)

### C-77: ~~Ledger archive retention unbounded~~ RESOLVED (accepted by design)
The existing 9-archive rotation cap in `_rotate_ledger()` (`digests_and_ledgers.py:163`) bounds disk usage at 720 MB worst case across all 8 ledger types. At current growth rates (530 KB total, ~1-2 KB per monthly run), this bound won't be reached for decades. Provenance is mission-critical — archives should be preserved for audit, not garbage-collected. 8/8 expert perspectives agree: the problem doesn't exist at current scale.
**Source:** Nygard (expert review #4), expert review #8 (unanimous)

### C-78: `_place_events_columnar` hard to test in isolation — [DEFER]
100 lines of columnar bin-assignment logic tested only indirectly through `compile_grid()`. Core algorithm (lat/lon -> pgid, date -> month_index) could be extracted into a pure function. **Trigger: extract `compute_bin_assignments()` when compilation tests exceed 5 seconds.**
**Source:** Feathers (expert review #4)

### C-79: Compilation/consolidation require real Parquet I/O in tests — [DEFER]
`compile_grid()` and `consolidate_ucdp()` always read from disk. No seam to inject mock reader. Tests create actual Parquet files. **Trigger: add `read_table_fn` parameter when test suite exceeds 30 seconds.**
**Source:** Feathers (expert review #4)

### C-80: Registry boilerplate duplicated 5x — [DEFER]
`sources/__init__.py`, `consolidators/__init__.py`, `builders/__init__.py`, `aggregation.py`, `survivorship.py` each implement identical dict-based registries (~60 LOC each, ~200 LOC total). **Trigger: extract `Registry[T]` generic class on 6th registry.**
**Source:** Martin (expert review #4)

### C-03: Protocol proliferation risk in synthetic module — [DEFER]
`src/datafactory_synthetic/ARCHITECTURE.md` plans 3 Protocols before any concrete implementation. Premature abstraction. **Trigger: defer Protocols until a second implementation is needed.**
**Source:** GoF, Hickey

### C-60: No health check output tested with mock ledgers — [DEFER]
`check_health.py` has no test verifying output parsing with stale/missing/failing ledgers. **Trigger: add when check_health.py is modified.**
**Source:** Nygard (test review)

### C-61: No schema evolution test — [DEFER]
No test for what happens when Parquet columns are added/removed between consolidation vintages. **Trigger: add before third data source.**
**Source:** Kleppmann (test review)

### C-81: ~~GAUL shapefile download has no retry logic~~ RESOLVED
`gaul_admin.py:_download_shapefile_zip()` now uses `request_with_retry` from `datafactory_http`, gaining exponential backoff retry consistent with all other downloaders.
**Source:** Tech debt cleanup 2026-03-27

### C-83: ~~Retry retries on 4xx client errors~~ RESOLVED
`request_with_retry` now catches `HTTPError` separately. 4xx responses (401, 404, etc.) raise immediately without retry. 5xx responses and connection errors still retry with backoff + jitter. C-72 (429 specifically) remains — `Retry-After` header parsing not yet implemented.
**Source:** Nygard, Hickey (expert review #7)

---

## Deferred by Design

### C-06: Provenance logic should be a composable utility
Every module independently calls `append_ledger_entry()` with its own format. A `@provenance` decorator or context manager would centralize ~50 lines of boilerplate across 4 modules. Accepted as explicit > implicit for now.
**Source:** Hickey

### C-07: Frozen dataclass pattern repeated
7 config classes follow the same frozen-dataclass-with-`__post_init__` pattern. No shared Protocol or base. A declarative validation approach or `ValidatedConfig` Protocol would reduce duplication. Accepted: explicit repetition is simple and readable.
**Source:** Hickey
