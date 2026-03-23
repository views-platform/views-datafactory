# Expert Review Concerns — Priority-Ranked

**Date:** 2026-03-17 (updated 2026-03-22)
**Source:** Multi-expert engineering review, repo assimilation, falsification audits, expert code review (Martin, GoF, Feathers, Nygard, Kleppmann, Ousterhout, Hickey, Beck)
**Status:** 66 concerns total: 50 resolved, 1 documented, 2 deferred by design, 13 open. 8 disagreements: 8 resolved.

**Ranking criteria:** Impact if wrong × likelihood × detectability. Items marked **[DEFER]** are accepted risks or wait for a specific trigger condition.

---

## Tier 1 — Fix Before Production

### C-42: ~~Bare `except Exception` in version discovery~~ RESOLVED
`ucdp_candidate.py:186` and `ucdp_dot9.py:203` narrowed from `except Exception` to `except (requests.RequestException, ValueError)`. Unexpected exceptions now propagate. Log level changed from INFO to DEBUG.
**Source:** Repo assimilation, tech debt audit, Nygard (expert review 6)

### C-43: ~~Candidate comparison result silently discarded~~ RESOLVED
All three harvesters now assign comparison result, log revision stats, and merge revision warnings into ledger entries. Candidate and dot9 aligned with annual's correct pattern.
**Source:** GoF, Feathers (expert review 6)

### D-03: Fail-loud vs. operational resilience
ADR-003/008 mandate fail-loud everywhere. Nygard asks what the operational experience is when the UCDP API is down for 3 days. For a production forecasting system, some resilience policy is needed — serve last-known-good with a warning flag, alert, or queue retry. **Resolution needed: define as a project-specific ADR before production deployment.**
**Source:** Nygard (expert reviews 4, 6)

---

## Tier 2 — Fix Before Scaling

### C-24: ~~Compiler loads entire Parquet into list-of-dicts~~ RESOLVED
Replaced with `_place_events_columnar()`: extracts only placement columns (lat, lon, date) as lists, computes bin assignments, then materializes full event dicts only for placed events. Avoids 19M-object upfront allocation.
**Source:** Repo assimilation, Kleppmann

### C-14: ~~JSONL provenance files are unbounded~~ RESOLVED
`append_ledger_entry()` now rotates the ledger when it exceeds 10 MB (`_MAX_LEDGER_BYTES`). Rotation shifts `ledger.jsonl` → `ledger.1.jsonl` → `ledger.2.jsonl` (max 9 archives). Current file stays bounded.
**Source:** Nygard

### C-16: ~~No concurrency model~~ RESOLVED
Advisory file locking via `fcntl.flock` added to `append_ledger_entry()` and `write_store()` via `file_lock()` context manager. Concurrent processes block on the lock rather than corrupting files.
**Source:** Kleppmann

### C-25: ~~Source digest reads entire file into memory~~ RESOLVED
New `compute_file_digest(path)` reads in 64KB chunks via `hashlib.update()`. Callers in `grid_compilation.py` and `event_store.py` updated. Original `compute_content_digest(bytes)` retained for in-memory data.
**Source:** Repo assimilation, Nygard

### C-26: ~~`_read_ledger_entries` reads entire JSONL file~~ RESOLVED
`last_digest()` now uses `_read_last_line()` which seeks to end of file and reads backwards in 4KB chunks — O(1) for the common case. Falls back to full read only if last line is malformed. `last_digest_for_version()` still uses full read (rare call, needs version scan).
**Source:** Repo assimilation, Kleppmann

---

## Tier 3 — Improve Quality

### C-47: ~~Three weak/tautological test assertions~~ RESOLVED
All three replaced with behavior-checking assertions: `test_harvester.py:134` checks `n_events` and `content_digest`; `test_consolidation.py:353` checks `output_path.exists()` and exact counts; `test_viewpoint.py:440` replaced `isinstance` with digest length check.
**Source:** Feathers, Beck (expert review 6)

### C-48: ~~Beige test coverage thin — boundary conditions missing~~ RESOLVED
Added `TestFilteringBeige` (3 tests: gid=0/1, tov=3/4, where_prec=3/4 boundaries) and `TestCompileGridBoundaryBeige` (2 tests: south pole placement, Dec/Jan year boundary).
**Source:** Beck (expert review 6)

### C-49: ~~Minimal test fixture infrastructure~~ RESOLVED
Added `make_ucdp_event()` and `write_test_parquet()` factories to `conftest.py`. Shared across viewpoint, consolidation, and compiler tests. Per-file helpers retained for module-specific setup.
**Source:** Feathers, Beck (expert review 6)

### C-21: No characterization tests for migration source — [DEFER]
The metric lab code being migrated has its own tests, but this repo has no "golden output" tests that capture expected behavior of migrated code. Migration without characterization tests risks silent behavioral divergence. **Trigger: when next migration batch is planned.**
**Source:** Feathers

### C-39: ~~No coordinate range validation~~ RESOLVED
Added coordinate range checks to `validate_events()`: lat outside [-90,90] and lon outside [-180,180] are recorded as warnings (same pattern as fatality bound checks). Warnings propagate to provenance ledger.
**Source:** Repo assimilation

### C-40: ~~Fatality count inequality not validated~~ RESOLVED
Already implemented in `validate_events()` lines 138-144: checks `best < 0`, `best > high`, `low > best` and records as warnings. Was incorrectly listed as unresolved — the validation existed before the concern was filed.
**Source:** Repo assimilation

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
All three UCDP harvesters follow config→fetch→validate→compare→archive→store→provenance but no shared template enforces step order. A 4th source author must read existing sources to discover the pattern. **Trigger: extract `HarvestPipeline` when a 4th source is added.**
**Source:** GoF (expert review 6)

### C-46: No ledger write idempotency — [DEFER]
`append_ledger_entry()` has no dedup key. Process crash after append but before caller return causes duplicate on retry. Ledger readers tolerate duplicates. **Trigger: consider when ledger is consumed by external systems requiring exactly-once semantics.**
**Source:** Kleppmann (expert review 6)

### C-32: Source registry returns `Any` — [DEFER]
`fetch_source` returns `Any` (widened from `Path` for candidate's `list[dict]`). Consumers can't rely on the return type. **Trigger: consider `SourceResult` union if type errors appear in consumer code.**
**Source:** GoF, Hickey (expert review 5)

### C-30: No performance test for full-scale compilation — [DEFER]
60-second target (NF-5: 259,200 cells × 432 months) has no test. Full-scale operation proven in practice (1.7M events, <60s). **Trigger: add performance test before CI/CD pipeline.**
**Source:** Repo assimilation, Nygard

### C-29: No end-to-end integration test — [DEFER]
Partially addressed by `test_integration.py` (100 events, realistic pipeline). Full-scale end-to-end with all 3 sources untested. **Trigger: add before production deployment.**
**Source:** Repo assimilation, Feathers

### C-28: Candidate source uses fake annual config workaround — [DEFER]
`ucdp_candidate.py:188-198` constructs `UcdpAnnualConfig(start_year=2000, end_year=2099)` to reuse `fetch_paginated`. Sends unnecessary 100-year date range. Works correctly. **Trigger: fix when extracting `_ucdp_common.py` (C-31).**
**Source:** Falsification audit DoD005

### C-27: Retry pattern duplicated in 2 modules — [DEFER]
`grid/harvester.py:52-75` and `ucdp_annual.py:132-163` implement the same exponential backoff. **Trigger: extract to core when a 3rd module needs it (DRY "third use" rule).**
**Source:** Repo assimilation, expert review 4

### C-41: Digest truncation collision risk — [DEFER]
`DIGEST_TRUNCATE = 16` hex chars = 64-bit space. 50% collision at ~4B items. Fine at ~2M events. **Trigger: consider when total records exceed 100M or digests are used as unique keys.**
**Source:** Repo assimilation

### C-38: Version string year offset assumes 21st century — [DEFER]
`_DOT9_YEAR_OFFSET = 2000` / `_CANDIDATE_YEAR_OFFSET = 2000` in `ucdp_dot9.py:50` and `ucdp_candidate.py:43`. Breaks silently for pre-2000 or post-2099 data. UCDP data starts 1989 (annual uses full version strings). **Trigger: never (2099 is 73 years away).**
**Source:** Repo assimilation

### C-10: Ontology vocabulary overhead — [DEFER]
Terms like "Source Nodes," "Compilation Edges," "Explicit Non-Entities" are precise but add conceptual overhead. For a 7-package project, governance is heavy. **Accepted: governance has proven itself (ADR-008 caught bugs in 3 audits). Cost is documentation maintenance, not development velocity.**
**Source:** Ousterhout

### C-03: Protocol proliferation risk in synthetic module — [DEFER]
`src/datafactory_synthetic/ARCHITECTURE.md` plans 3 Protocols before any concrete implementation. Premature abstraction. **Trigger: defer Protocols until a second implementation is needed.**
**Source:** GoF, Hickey

### C-50: ~~Per-file test helpers duplicate conftest factories~~ RESOLVED
Per-file helper `_make_consolidated_event` has different default metadata fields (`_harvest_digest`, `_harvest_timestamp`) than the conftest factory. The duplication is justified — different defaults serve different test needs. Accepted.
**Source:** Feathers (expert review #2)

### C-51: ~~No health check script for operator visibility~~ RESOLVED
`scripts/check_health.py` reads all ledger files, reports last-successful timestamp per source, warns on stale data (>7 days).
**Source:** Nygard (expert review #2)

### C-52: ~~Parquet schema evolution undocumented~~ RESOLVED
Documented in ADR-013 Notes section: new columns appear via `promote_options="default"`, removed columns leave nulls, incompatible types raise errors.
**Source:** Kleppmann (expert review #2)

### C-53: ~~No tests for export_dataframe.py or verify_parity.py~~ RESOLVED
`tests/test_scripts.py` validates all scripts: existence, syntax (AST parse), `main()` function, `__name__` guard, argparse usage.
**Source:** Beck (expert review #2)

### C-54: ~~Falsification stub retirement policy~~ RESOLVED
Policy defined: resolved stubs become passing assertions. Empirical data stubs (11 current) are retained as audit trail documenting UCDP data characteristics. Archive only when superseded by new data.
**Source:** Beck (expert review #2)

### C-55: ~~No Red tests for FeatureFrame~~ RESOLVED
Added `TestFeatureFrameRed` (zero rows, save to deep directory) in `test_adapters.py`.
**Source:** Beck, Leveson (test review)

### C-56: ~~No direct tests for land_mask.py~~ RESOLVED
Added `tests/test_land_mask.py` with Green (API fetch, cache reuse, force refresh) and Beige (empty cache creates new).
**Source:** Beck (test review)

### C-57: ~~`_compute_month_ids` tested for 1 date only~~ RESOLVED
Added `TestMonthIdBeige` with 4 tests: epoch boundary (Jan 1980), before epoch (Dec 1979), full range (1989-2026), raw vs VIEWS comparison.
**Source:** Kleppmann (test review)

### C-58: ~~No adapter roundtrip test~~ RESOLVED
Added `TestAdapterRoundtripGreen` with grid→DF→FF consistency check and FeatureFrame save→load→verify roundtrip.
**Source:** Feathers (test review)

### C-59: ~~`ceil_split` with `best=0` untested~~ RESOLVED
Added `test_best_zero_multi_month_not_summary` in `TestCeilSplitGreen`. Verifies `best=0, span=3` is NOT detected as summary (best < span), returns single row.
**Source:** Leveson (test review)

### C-60: No health check output tested with mock ledgers — [DEFER]
`check_health.py` has no test verifying output parsing with stale/missing/failing ledgers. **Trigger: add when check_health.py is modified.**
**Source:** Nygard (test review)

### C-61: No schema evolution test — [DEFER]
No test for what happens when Parquet columns are added/removed between consolidation vintages. **Trigger: add before third data source.**
**Source:** Kleppmann (test review)

### C-62: ~~grid_to_dataframe/feature_frame share duplicated flatten logic~~ RESOLVED
Extracted `_flatten_grid()` helper used by both `grid_to_dataframe` and `grid_to_feature_frame`.
**Source:** Hickey, Martin (expert review #3)

### C-63: ~~check_health.py lacks machine-readable output~~ RESOLVED
Added `--json` flag to `check_health.py`. Outputs `{timestamp, healthy, sources}` JSON for monitoring integration.
**Source:** Nygard (expert review #3)

### C-64: ~~FeatureFrame.from_grid classmethod missing~~ RESOLVED
Added `FeatureFrame.from_grid()` classmethod wrapping `grid_to_feature_frame`. Keeps flattening convention in the class.
**Source:** GoF (expert review #3)

### C-65: ~~FeatureFrame shape mismatch with PredictionFrame untested~~ RESOLVED
Added `TestIdentifierAlignmentGreen` verifying FeatureFrame's `REQUIRED_IDENTIFIERS` includes `time` and `unit`, matching PredictionFrame's convention.
**Source:** Failure mode analysis (expert review #3)

### C-66: concerns00.md has no machine-readable index — [DEFER]
61+ concerns in one markdown file (~300 lines). Finding specific items requires reading the whole file. No JSON/YAML index for programmatic access. **Trigger: consider when concern count exceeds 75.**
**Source:** Ousterhout (expert review #3)

### D-08: ~~Shared flatten logic — DRY vs YAGNI~~ RESOLVED
Hickey and Martin both see duplicated flatten logic in adapter conversions. Both agree extraction would help. **Resolution: extract `_flatten_grid` when 3rd conversion function appears. Currently 2 functions — premature to extract.**
**Source:** Expert review #3

### C-06: Provenance logic should be a composable utility — [DEFERRED BY DESIGN]
Every module independently calls `append_ledger_entry()` with its own format. A `@provenance` decorator or context manager would centralize ~50 lines of boilerplate across 4 modules. Accepted as explicit > implicit for now.
**Source:** Hickey

### C-07: Frozen dataclass pattern repeated — [DEFERRED BY DESIGN]
7 config classes follow the same frozen-dataclass-with-`__post_init__` pattern. No shared Protocol or base. A declarative validation approach or `ValidatedConfig` Protocol would reduce duplication. Accepted: explicit repetition is simple and readable.
**Source:** Hickey

---

## Expert Disagreements

### D-01: ~~Governance proportionality~~ RESOLVED
Ousterhout: 18 ADRs + 12 CICs for 36 source files is heavyweight. Beck: governance has proven itself — ADR-008 caught bugs in 3 consecutive audits. **Resolution: governance stays. Cost is documentation maintenance, not velocity.**

### D-02: ~~Early Protocols vs. YAGNI~~ RESOLVED
GoF: extract Protocols for strategy patterns. Hickey: plain functions work. **Resolution: aggregation strategies are plain functions, no Protocols needed. Extract when second source needs different signatures.**

### D-03: ~~Fail-loud vs. operational resilience~~ RESOLVED (ADR-018)
ADR-018 defines operational resilience policy: pipeline stays fail-loud (ADR-008/011 unchanged), operators may serve bounded-stale data under documented conditions (provenance audit, staleness threshold, freshness indicator, alert escalation). No code changes to pipeline.
**Source:** Nygard (expert reviews 4, 6)

### D-04: ~~Tests-first vs. characterization-first~~ RESOLVED
Beck: write specification tests now. Feathers: capture metric lab behavior first. **Resolution: both valid — spec tests define target, characterization tests verify migration.**

### D-05: ~~Registry duplication — DRY vs simplicity~~ RESOLVED
Martin: 3 identical registries violate DRY; extract `PluginRegistry`. Hickey: 3 copies are explicit, readable, no framework. **Resolution: accept at current scale. Extract on 4th registry.**
**Source:** Expert review 6

### D-06: ~~Filter extensibility — chain vs if-statements~~ RESOLVED
GoF: sequential if-checks need Chain-of-Responsibility. Hickey: 3 filters don't justify the abstraction. **Resolution: accept if-statements. Extract chain on 5th filter.**
**Source:** Expert review 6

### D-07: ~~Distributed provenance vs. centralized decorator~~ RESOLVED
Hickey: every module calls `append_ledger_entry()` independently. A `@provenance` decorator would centralize. Martin: explicit is better at this scale. **Resolution: accept distributed pattern. Same rationale as C-06 (deferred by design).**
**Source:** Expert review #2

---

## Resolved Concerns (Reference)

| ID | Title | Resolution |
|----|-------|------------|
| C-01 | No DAG enforcement beyond tests | Import-enforcement test in `test_import_enforcement.py` |
| C-02 | Dual version source | `pyproject.toml` and `__init__.py` both declare `0.1.0` |
| C-04 | No factory/registry for sources | Dict-based source registry implemented |
| C-05 | SpatioTemporalGrid contract unclear | CIC created at `docs/CICs/SpatioTemporalGrid.md` |
| C-08 | Doc complexity exceeds code complexity | Ratio improved to ~3:1 as codebase grew |
| C-09 | ARCHITECTURE.md duplicates ADR content | Acknowledged; considered referencing by number |
| C-11 | Governance should prove itself | Audit completed; ADR-008 alone exceeds governance cost |
| C-12 | No retry policy for API calls | Exponential backoff (`2**attempt`) implemented |
| C-13 | No timeout declarations | Configurable in UcdpAnnualConfig (30s default) |
| C-15 | No graceful degradation path | ADR-011: fail-loud, no stale serving |
| C-17 | Revision storage semantics | `archive_snapshot` + `ComparisonResult` tracking |
| C-18 | Schema evolution of ledgers unplanned | `LEDGER_VERSION=1` added |
| C-19 | Deterministic compilation untested | `test_deterministic` verifies identical digests |
| C-20 | Ledger corruption on process kill | `_read_ledger_entries` skips malformed lines |
| C-22 | No red/beige/green test structure | `TestXxxGreen/Beige/Red` naming convention |
| C-23 | `network` marker unused | Dead config removed |
| C-33 | Discovery probes had no rate limiting | `time.sleep(0.5)` between probes |
| C-34 | Global mutable registry — test pollution | `_clear_registry()` + conftest fixture |
| C-35 | Digest algorithm not recorded | `DIGEST_SCHEME` added to entries |
| C-42 | Bare `except Exception` in discovery | Narrowed to `(RequestException, ValueError)` |
| C-43 | Candidate comparison result discarded | All 3 harvesters now assign, log, and record warnings |
| C-14 | JSONL ledgers unbounded | Rotation at 10 MB threshold |
| C-16 | No concurrency model | Advisory file locking via `fcntl.flock` |
| C-24 | Compiler list-of-dicts memory | Columnar placement with deferred dict materialization |
| C-25 | Source digest reads entire file | Chunked `compute_file_digest()` |
| C-26 | Ledger reads O(n) | Reverse-read `_read_last_line()` for `last_digest()` |
| C-39 | No coordinate range validation | Lat/lon range checks in `validate_events()` |
| C-40 | Fatality inequality not validated | Already existed in `validate_events()` |
| C-47 | Weak test assertions | Replaced with behavior-checking assertions |
| C-48 | Thin Beige test coverage | Added boundary tests for filters and grid placement |
| C-49 | Minimal fixture infrastructure | Shared factories in `conftest.py` |
