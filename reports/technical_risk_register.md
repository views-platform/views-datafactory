# Technical Risk Register

**Date:** 2026-03-17 (updated 2026-04-06)
**Source:** Multi-expert engineering review, repo assimilation, falsification audits, expert code review (Martin, GoF, Feathers, Nygard, Kleppmann, Ousterhout, Hickey, Beck)
**Status:** 113 concern IDs assigned (C-28 merged into C-31, C-107 merged into C-60): 73 resolved, 32 open/deferred (2 with fired triggers accepted at v1.0), 6 accepted by design. 17 disagreements: 17 resolved.
**Archive:** Resolved concerns and disagreements are in `technical_risk_register_resolved.md`.

**Ranking criteria:** Impact if wrong x likelihood x detectability. Items marked **[DEFER]** are accepted risks or wait for a specific trigger condition. See ADR-020 for governance rationale.

---

## Open Items Summary

| ID | Tier | Title | Trigger | Package |
|----|------|-------|---------|---------|
| C-84 | 2 | Server runs everything as root | Before 2nd user access | Server hardening |
| C-85 | 2 | Personal GitHub SSH key on shared server | Before 2nd user access | Server hardening |
| C-86 | 2 | No deploy key — repo access tied to personal account | Before 2nd user access | Server hardening |
| C-87 | 2 | No named user accounts on server | Before 2nd user access | Server hardening |
| C-88 | 2 | SSH not restricted to PRIO/Uppsala IPs | Before production deployment | Server hardening |
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
| C-60 | 4 | Health check logic untested (incl. C-107) | check_health.py modified | Test infra |
| C-91 | 4 | No pipeline duration tracking | Before adding V-Dem or ACLED | V-Dem readiness |
| C-93 | 4 | `_count_outcomes` mixes raw counts with derived computation | When harvest reporting is refactored | Code cleanup |
| C-96 | 4 | fsspec does not auto-read `~/.netrc` | If fsspec adds netrc support | — |
| C-97 | 4 | Basic auth + Caddy scalability ceiling at ~30-50 users | Before consumer count exceeds 30 | — |
| C-104 | 4 | Date string format assumed YYYY-MM-DD throughout | New data source with different format | V-Dem readiness |
| C-105 | 4 | Assembly mmap write is not atomic | Disk fills during assembly step | — |
| C-106 | 4 | `_source_version` parsing assumes dotted-integer format | Non-numeric version segments | V-Dem readiness |
| C-108 | 4 | Parquet and zarr exports serve different feature sets | Consumer expects parity | — |
| C-109 | 4 | Advisory file locks (fcntl) don't work across NFS | Pipeline migrates to network FS | — |
| C-112 | 4 | Duplicate dimensionality validation across adapter files | Next adapter refactor | Code cleanup |
| C-113 | 4 | Inconsistent HTTP timeout values across sources | Before adding V-Dem or ACLED | V-Dem readiness |
| C-10 | — | Ontology vocabulary overhead | Accepted | — |
| C-38 | — | Version string year offset assumes 21st century | Never (2099) | — |
| C-41 | — | Digest truncation collision risk | Records exceed 100M | — |
| C-06 | — | Provenance composability | Deferred by design | — |
| C-07 | — | Frozen dataclass pattern repeated | Deferred by design | — |

## Work Packages

Items that should be resolved together:

| Package | Items | Trigger |
|---------|-------|---------|
| **Server hardening** | C-84, C-85, C-86, C-87, C-88 | Before 2nd user access |
| **V-Dem readiness** | C-44, C-91, C-104, C-106, C-113 | Before V-Dem integration (C-102 resolved) |
| **UCDP API resilience** | C-70, C-72 | Multi-operator deployment |
| **UCDP schema defense** | C-36, C-37, C-45 | UCDP API change |
| **Test infrastructure** | C-29, C-60, C-78, C-79 | Test suite growth |
| **Code cleanup** | C-31, C-93, C-112 | Next refactor opportunity (C-80 resolved) |

---

## Tier 2 — Fix Before Sharing Server Access

### C-84: Server runs everything as root — [DEFER]
All pipeline operations, git, and Caddy configuration run as `root` on the Hetzner server. No separation of privileges. A mistake as root can destroy the OS. IT head explicitly advised "limit who can sudo." **Trigger: create a non-root service account (e.g., `views-deploy`) before granting anyone else server access.** Procedure documented in `hetzner_deployment_guide.md` Phase 6.1.
**Source:** PRIO IT security guidance, server setup 2026-03-28

### C-85: Personal GitHub SSH key on shared server — [DEFER]
The server's SSH key (`/root/.ssh/id_ed25519`) is registered on Simon's personal GitHub account. If another user gets root access, they effectively have Simon's GitHub credentials for all repos. **Trigger: replace with a repo-scoped deploy key before granting second user access.** Procedure documented in `hetzner_deployment_guide.md` Phase 6.2.
**Source:** Server setup 2026-03-28

### C-86: No deploy key — repo access tied to personal account — [DEFER]
GitHub access from the server uses a personal SSH key, not a deploy key. Deploy keys are scoped to a single repo, are read-only by default, and don't grant access to other repos on the account. **Trigger: create a GitHub deploy key for `views-platform/views-datafactory` and remove the personal key from the server.** Procedure documented in `hetzner_deployment_guide.md` Phase 6.2.
**Source:** Server setup 2026-03-28

### C-87: No named user accounts on server — [DEFER]
Only `root` exists. IT head advised: named accounts per person, no shared accounts, plus a break-glass emergency account with securely stored credentials. **Trigger: create named accounts before granting second user access.** Procedure documented in `hetzner_deployment_guide.md` Phase 6.3.
**Source:** PRIO IT security guidance, server setup 2026-03-28

### C-88: SSH not restricted to PRIO/Uppsala IPs — [DEFER]
SSH is open to all source IPs. IT head advised whitelisting PRIO and Uppsala VPN IPs via fail2ban or Hetzner firewall, requiring VPN for SSH access. **Trigger: configure before production deployment.** Procedure documented in `hetzner_deployment_guide.md` Phase 6.4. Requires PRIO/Uppsala VPN CIDR ranges from IT.
**Source:** PRIO IT security guidance, server setup 2026-03-28

---

## Tier 3 — Improve Quality

### C-21: No characterization tests for migration source — [DEFER]
The metric lab code being migrated has its own tests, but this repo has no "golden output" tests that capture expected behavior of migrated code. Migration without characterization tests risks silent behavioral divergence. **Trigger: when next migration batch is planned.**
**Source:** Feathers

---

## Tier 4 — Accept or Defer

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
Callers must know magic strings (`"count"`, `"sum_best"`, `"max_best"`) and filter dict syntax. No IDE discoverability. **Trigger: consider enum-based strategy names if user confusion is observed.**
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

### C-60: Health check logic untested — [DEFER]
`check_health.py` (236 LOC) has no test verifying output parsing with stale/missing/failing ledgers. A bug here could mask pipeline failures or produce false "all healthy" reports. **Trigger: add mock-ledger tests when check_health.py is modified.**
**Source:** Nygard (test review), repo assimilation 2026-04-04 (incorporates former C-107)

### C-91: No pipeline duration tracking — [DEFER]
A clean pipeline run takes ~2.5 hours but there's no mechanism to track whether it's getting slower over time. Kleppmann (Ch.1 p.13) argues performance should be measured as a distribution (percentiles, not averages) and tracked over time. Ch.8 pp.281-283 notes that timeouts are the only reliable fault detector — without duration tracking, a pipeline that silently doubles in runtime is indistinguishable from one that's about to fail. **Trigger: add timing to provenance ledger before adding V-Dem or ACLED.**
**Source:** DDIA Ch.1 p.13, Ch.8 pp.281-283.

### C-93: `_count_outcomes` mixes raw counts with derived computation — [DEFER]
`harvest_ucdp.py:_count_outcomes()` counts raw outcome categories (`cached`, `success`, `unchanged`, `failed`, `not_served`) then adds a computed `"served"` key (`len(results) - not_served`). Mixing enumeration with derivation in a counting function is a minor naming/responsibility ambiguity. **Trigger: refactor when harvest reporting logic is next modified.**
**Source:** PR #2 code review 2026-03-30

### C-96: fsspec does not auto-read `~/.netrc` — [DEFER]
fsspec's HTTPFileSystem does not read `~/.netrc` or set `trust_env=True` on its aiohttp session. xarray consumers must pass auth explicitly via `storage_options={"client_kwargs": {"auth": (user, pass)}}`. The `verify_remote.py` script reads netrc programmatically via Python's `netrc` module, but the primary consumer path (xarray + fsspec + zarr) does not benefit from it automatically. Consumer guide should provide a helper pattern. **Trigger: simplify consumer guide if fsspec adds netrc/trust_env support.**
**Source:** Falsification audit 2026-04-01 (F3)

### C-97: Basic auth + Caddy scalability ceiling at ~30-50 users — [DEFER]
Caddy's `basic_auth` stores username/bcrypt-hash pairs in a flat Caddyfile. No audit trail (who accessed what, when), no per-user rate limiting, no credential rotation, no MFA. Acceptable for a small research team (5-20 users). Breaks down at 30-50 users when credential management, audit requirements, and revocation coordination become operational burdens. Migration path: Caddy `forward-auth` directive + oauth2-proxy with institutional SSO (PRIO/Uppsala). **Trigger: before consumer count exceeds 30, or before institutional audit/compliance requirements emerge.**
**Source:** Falsification audit 2026-04-01 (F2)

### C-104: Date string format assumed YYYY-MM-DD throughout temporal pipeline — [DEFER]
`_parse_month_index()`, `_month_first_day()`, and `_months_between()` in `grid_compilation.py` and `temporal_distribution.py` all split date strings on `"-"` and extract year/month by position. No format validation at the ingestion boundary. A new data source producing ISO 8601 with time components (e.g., `2023-03-15T00:00:00`) would partially parse but `_months_between` output wouldn't round-trip. UCDP consistently uses `YYYY-MM-DD`. **Trigger: add format validation when integrating V-Dem, ACLED, or any non-UCDP source.**
**Source:** Repo assimilation 2026-04-04 (Phase 5, invariant 5)

### C-105: Assembly mmap write is not atomic — partial grid on disk full — [DEFER]
`assemble_grid.py:211` uses `np.lib.format.open_memmap` to create a 19 GB output file. If disk fills during the write, a half-written `grid.npy` remains on disk with no rollback mechanism. The provenance digest computation would fail (can't hash incomplete file), but the corrupted file exists and downstream scripts may find it. Kleppmann (Ch.7 pp.223-226) defines atomicity as "all or nothing" — either the entire write completes or none of it does. Ch.10 p.413 describes the batch output pattern: write to a temporary location, then atomically rename into place. This is the recommended fix: write to `grid.npy.tmp`, then `os.rename()` on success. **Trigger: add disk space pre-check when server storage drops below 40 GB free, or implement write-to-temp-then-rename.**
**Source:** Repo assimilation 2026-04-04 (Phase 5, invariant 14). DDIA Ch.7 pp.223-226, Ch.10 p.413.

### C-106: `_source_version` parsing assumes dotted-integer format — [DEFER]
`survivorship.py:_parse_version()` calls `int()` on each `.`-split part of a version string. A version like `"25.1-beta"` would raise `ValueError` with no try/except in the survivorship strategies. All current UCDP versions use dotted integers (e.g., `"25.1"`, `"25.0.12"`, `"25.9.1"`). **Trigger: add error handling when integrating a source with non-numeric version strings.**
**Source:** Repo assimilation 2026-04-04 (Phase 5, invariant 7)

### C-108: Parquet and zarr exports serve different feature sets — [DEFER]
`export_dataframe.py` defaults to `--input data/compiled` (6 UCDP features), while `export_zarr.py` defaults to `--input data/assembled` (43 features including PRIO-GRID static + GAUL admin). A consumer using the parquet endpoint gets a different feature set than one using zarr. This may be intentional (parquet = conflict-only, zarr = full grid) but is not documented. The `data_serving_guide.md` and `zarr_consumer_guide.md` do not mention the difference. **Trigger: document the intended asymmetry, or align both exports to data/assembled.**
**Source:** Repo assimilation 2026-04-04 (Phase 3)

### C-109: Advisory file locks (fcntl) don't work across NFS — [DEFER]
`file_lock()` in `digests_and_ledgers.py` uses `fcntl.flock` which is advisory and may not work on network filesystems (NFS, CIFS). Currently deployed on local SSD on the Hetzner server. A migration to shared/network storage would silently break concurrency protection for ledger writes. Kleppmann (Ch.7 pp.234-236) describes read-committed isolation via locks — our fcntl.flock achieves this at the file level on local disk. Ch.8 pp.301-303 introduces fencing tokens as a safety mechanism when locks can be stale: a monotonically increasing token ensures an expired lock holder cannot perform writes. This pattern would be needed if we migrate to network storage. **Trigger: verify lock behavior before migrating to network-attached storage or multi-server deployment.**
**Source:** Repo assimilation 2026-04-04 (Phase 5, invariant 10). DDIA Ch.7 pp.234-236, Ch.8 pp.301-303.

### C-112: Duplicate dimensionality validation across adapter files — [DEFER]
The dimensionality validation helper in `grid_to_dataframe.py`, `grid_to_feature_frame.py`, and `feature_frame.py` contains identical logic (check ndim == 3, verify shape matches config). Three copies of ~10 lines. Not dangerous — the logic is simple and stable — but a maintenance concern if the grid contract (cells, time, features) ever changes. **Trigger: extract a shared validator into `datafactory_adapters` when the next adapter refactor occurs.**
**Source:** Tech debt cleanup 2026-04-06

### C-113: Inconsistent HTTP timeout values across sources — [DEFER]
Each harvester source defines its own HTTP timeout: UCDP annual uses 30s, UCDP candidate 30s, UCDP .9 uses 60s, PRIO-GRID static 120s, GAUL 90s. These values evolved independently and are not documented as intentional policy. For current sources this works — PRIO-GRID and GAUL payloads are legitimately larger. But adding a new source requires guessing a timeout. **Trigger: before adding V-Dem or ACLED, define a timeout policy (e.g., per-payload-size tiers) and document it in ADR-018 or a dedicated ADR.**
**Source:** Tech debt cleanup 2026-04-06

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
