# Technical Risk Register — Resolved Archive

Historical record of resolved concerns and expert disagreements.
Active concerns are in `technical_risk_register.md`.

---

## Resolved Concerns

### Tier 1 (Fixed Before Production)

### C-42: ~~Bare `except Exception` in version discovery~~ RESOLVED
`ucdp_candidate.py:186` and `ucdp_dot9.py:203` narrowed from `except Exception` to `except (requests.RequestException, ValueError)`. Unexpected exceptions now propagate. Log level changed from INFO to DEBUG.
**Source:** Repo assimilation, tech debt audit, Nygard (expert review 6)

### C-43: ~~Candidate comparison result silently discarded~~ RESOLVED
All three harvesters now assign comparison result, log revision stats, and merge revision warnings into ledger entries. Candidate and dot9 aligned with annual's correct pattern.
**Source:** GoF, Feathers (expert review 6)

### C-67: ~~Parquet store write is not atomic~~ RESOLVED
`write_store()` in `event_store.py` wrote directly to the target path. A crash mid-write corrupts the store with no recovery path. **Fix:** write to temp file then `os.rename()` for atomic replacement.
**Source:** Kleppmann (expert review #4), long-term regret test

### C-68: ~~File lock has no staleness check~~ RESOLVED
`file_lock()` in `digests_and_ledgers.py` uses `fcntl.flock(LOCK_EX)` which blocks indefinitely. A process crash while holding the lock leaves a stale `.lock` file — all subsequent ledger writes hang forever. **Fix:** check `.lock` file age before blocking; warn and remove if older than 5 minutes.
**Source:** Nygard (expert review #4), failure mode analysis

### C-69: ~~No schema fingerprint in consolidation ledger~~ RESOLVED
Consolidation ledger entries had no record of the Parquet schema. Schema changes from UCDP (field additions/removals) were invisible until downstream failures. **Fix:** record `schema_fingerprint` (sorted column names hash) in each consolidation ledger entry.
**Source:** Kleppmann (expert review #4), long-term regret test

### C-27: ~~Retry pattern duplicated in 3 modules~~ RESOLVED
Extracted `request_with_retry` to new Layer 0 package `datafactory_http`. All callers (`ucdp_annual`, `ucdp_candidate`, `ucdp_dot9`, `shapefile_harvester`, `gaul_admin`) now import from the shared module.
**Source:** Repo assimilation, expert review 4, tech debt cleanup 2026-03-27

### Tier 2 (Fixed Before Scaling)

### C-24: ~~Compiler loads entire Parquet into list-of-dicts~~ RESOLVED
Replaced with `_place_events_columnar()`: extracts only placement columns (lat, lon, date) as lists, computes bin assignments, then materializes full event dicts only for placed events. Avoids 19M-object upfront allocation.
**Source:** Repo assimilation, Kleppmann

### C-14: ~~JSONL provenance files are unbounded~~ RESOLVED
`append_ledger_entry()` now rotates the ledger when it exceeds 10 MB (`_MAX_LEDGER_BYTES`). Rotation shifts `ledger.jsonl` -> `ledger.1.jsonl` -> `ledger.2.jsonl` (max 9 archives). Current file stays bounded.
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

### Tier 3 (Quality Improvements)

### C-47: ~~Three weak/tautological test assertions~~ RESOLVED
All three replaced with behavior-checking assertions: `test_harvester.py:134` checks `n_events` and `content_digest`; `test_consolidation.py:353` checks `output_path.exists()` and exact counts; `test_viewpoint.py:440` replaced `isinstance` with digest length check.
**Source:** Feathers, Beck (expert review 6)

### C-48: ~~Beige test coverage thin — boundary conditions missing~~ RESOLVED
Added `TestFilteringBeige` (3 tests: gid=0/1, tov=3/4, where_prec=3/4 boundaries) and `TestCompileGridBoundaryBeige` (2 tests: south pole placement, Dec/Jan year boundary).
**Source:** Beck (expert review 6)

### C-49: ~~Minimal test fixture infrastructure~~ RESOLVED
Added `make_ucdp_event()` and `write_test_parquet()` factories to `conftest.py`. Shared across viewpoint, consolidation, and compiler tests. Per-file helpers retained for module-specific setup.
**Source:** Feathers, Beck (expert review 6)

### C-39: ~~No coordinate range validation~~ RESOLVED
Added coordinate range checks to `validate_events()`: lat outside [-90,90] and lon outside [-180,180] are recorded as warnings (same pattern as fatality bound checks). Warnings propagate to provenance ledger.
**Source:** Repo assimilation

### C-40: ~~Fatality count inequality not validated~~ RESOLVED
Already implemented in `validate_events()` lines 138-144: checks `best < 0`, `best > high`, `low > best` and records as warnings. Was incorrectly listed as unresolved — the validation existed before the concern was filed.
**Source:** Repo assimilation

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
Added `TestAdapterRoundtripGreen` with grid->DF->FF consistency check and FeatureFrame save->load->verify roundtrip.
**Source:** Feathers (test review)

### C-59: ~~`ceil_split` with `best=0` untested~~ RESOLVED
Added `test_best_zero_multi_month_not_summary` in `TestCeilSplitGreen`. Verifies `best=0, span=3` is NOT detected as summary (best < span), returns single row.
**Source:** Leveson (test review)

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

### C-66: ~~concerns00.md scaling~~ RESOLVED
Concern count exceeded 75 trigger. Split into `technical_risk_register.md` (active) + `technical_risk_register_resolved.md` (archive). Formalized as governance artifact in ADR-020.
**Source:** Ousterhout (expert review #3)

### C-71: ~~No retry jitter~~ RESOLVED
Added `random.uniform(0, 1)` jitter to exponential backoff in `datafactory_http/retry.py`. Delay is now `2^attempt + random(0, 1)` instead of fixed `2^attempt`.
**Source:** Nygard (expert review #4)

### C-73: ~~Grid shape transposition produces silent wrong results~~ RESOLVED
Added shape validation (ndim + spatial dim match) to `_flatten_grid()`, `feature_frame_to_grid()`, and `FeatureFrame.from_grid()`. Transposed grids, 3D grids, and 1D pgids now raise `ValueError`. Retired `visualize_grid.py` (superseded scaffolding with live indexing bugs from an older grid convention).
**Source:** Ousterhout (expert review #4), failure mode analysis

### C-76: ~~Falsification tests are skipped, not running~~ RESOLVED
Registered `falsification` pytest marker. 11 stubs now use `@pytest.mark.falsification()` instead of `@pytest.mark.skip()`. Auto-skipped by default; visible with `--run-falsification`. Normal `pytest` output shows 0 skipped.
**Source:** Beck (expert review #4)

### C-77: ~~Ledger archive retention unbounded~~ RESOLVED (accepted by design)
The existing 9-archive rotation cap in `_rotate_ledger()` (`digests_and_ledgers.py:163`) bounds disk usage at 720 MB worst case across all 8 ledger types. At current growth rates (530 KB total, ~1-2 KB per monthly run), this bound won't be reached for decades. Provenance is mission-critical — archives should be preserved for audit, not garbage-collected. 8/8 expert perspectives agree: the problem doesn't exist at current scale.
**Source:** Nygard (expert review #4), expert review #8 (unanimous)

### C-81: ~~GAUL shapefile download has no retry logic~~ RESOLVED
`gaul_admin.py:_download_shapefile_zip()` now uses `request_with_retry` from `datafactory_http`, gaining exponential backoff retry consistent with all other downloaders.
**Source:** Tech debt cleanup 2026-03-27

### C-82: ~~No GAUL retry integration test~~ RESOLVED
Added `test_gaul_admin.py` with `test_retries_on_transient_failure` (verifies `_download_shapefile_zip` retries via `request_with_retry`) and `test_skips_download_when_cached` (verifies cache-hit path).
**Source:** Feathers, Beck, Nygard (expert review #7)

### C-83: ~~Retry retries on 4xx client errors~~ RESOLVED
`request_with_retry` now catches `HTTPError` separately. 4xx responses (401, 404, etc.) raise immediately without retry. 5xx responses and connection errors still retry with backoff + jitter. C-72 (429 specifically) remains — `Retry-After` header parsing not yet implemented.
**Source:** Nygard, Hickey (expert review #7)

### C-90: ~~Pipeline runs as interactive session, not a service~~ RESOLVED
Cron job set up on Hetzner: `0 0 21 * * cd /root/views-datafactory && bash scripts/refresh_pipeline.sh >> logs/refresh.log 2>&1`. Pipeline now runs automatically on the 21st of every month at midnight UTC. Three cron environment issues fixed: PATH (uv not found), PS1 unbound variable, and UCDP_API_TOKEN unreachable after .bashrc guard. `refresh_pipeline.sh` now sources `~/.profile` and exports PATH explicitly.
**Source:** DDIA literature alignment 2026-03-30, cron setup 2026-03-31

### C-94: ~~Shapefile harvester skips extraction when files missing but ledger has digest~~ RESOLVED
After data wipe, the provenance ledger survived with a valid digest. The shapefile harvester downloaded the ZIP, found the digest unchanged, and returned without extracting — assuming files were on disk. They weren't. Fixed by adding `files_on_disk` check to the "unchanged" code path: `shp_dir.exists() and any(shp_dir.glob("*.shp"))`.
**Source:** Cron pipeline failure 2026-03-31

### C-95: ~~Other harvesters may have same stale-ledger-vs-missing-files bug~~ RESOLVED
Audited and patched all 5 harvesters with the same `snap_path.exists()` check: `priogrid_static.py` (confirmed failing on cron run), `ucdp_candidate.py`, `ucdp_dot9.py`, `gaul_admin.py`. `ucdp_annual.py` was clean — it always writes regardless of digest. Pattern: every "unchanged" code path now verifies the output file exists before skipping the write.
**Source:** Cron pipeline failure 2026-03-31, systematic audit

### C-99: ~~No log rotation for pipeline logs~~ RESOLVED
`/etc/logrotate.d/views-datafactory` configured on Hetzner server. Verified 2026-04-04. The risk register entry was stale; the deployment log was correct.
**Source:** Falsification audit 2026-04-01, server verification 2026-04-04

### C-100: ~~Stale smoke_test.py reference in verify_parity.py~~ RESOLVED
`scripts/verify_parity.py` docstring referenced the retired `smoke_test.py` (line 11: "Requires data from prior smoke test") and used the old filename `parity_test.py` (line 5). Both updated.
**Source:** Tech debt cleanup 2026-04-02

### C-101: ~~3x duplicated min/max date code with type: ignore~~ RESOLVED
`ucdp_annual.py:295`, `ucdp_candidate.py:286`, and `ucdp_dot9.py:301` each had identical 6-line blocks extracting min/max date strings from event lists with `# type: ignore[type-var]`. Extracted `date_range()` helper to `event_validation.py` — returns typed `tuple[str | None, str | None]`, eliminates all 3 type ignores.
**Source:** Tech debt cleanup 2026-04-02

---

## Resolved Concerns (Early — Reference Table)

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

---

## Resolved Expert Disagreements

### D-01: ~~Governance proportionality~~ RESOLVED
Ousterhout: 18 ADRs + 12 CICs for 36 source files is heavyweight. Beck: governance has proven itself — ADR-008 caught bugs in 3 consecutive audits. **Resolution: governance stays. Cost is documentation maintenance, not velocity.**

### D-02: ~~Early Protocols vs. YAGNI~~ RESOLVED
GoF: extract Protocols for strategy patterns. Hickey: plain functions work. **Resolution: aggregation strategies are plain functions, no Protocols needed. Extract when second source needs different signatures.**

### D-03: ~~Fail-loud vs. operational resilience~~ RESOLVED (ADR-018)
ADR-003/008 mandate fail-loud everywhere. Nygard asked what the operational experience is when the UCDP API is down for 3 days. **All components now in place:**
- Policy: ADR-018 (operator-mediated bounded staleness, 7-day threshold)
- `harvest_ucdp.py` exits non-zero on harvest failure
- `refresh_pipeline.sh` has ERR trap with `pipeline_failure.json` sentinel + optional email
- `check_health.py` reports staleness and recent failures
- `export_zarr.py` writes `export_timestamp` (ISO 8601 UTC) to zarr attributes — consumers can verify freshness programmatically
**Source:** Nygard (expert reviews 4, 6, 7). Freshness indicator added 2026-04-02.

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

### D-08: ~~Shared flatten logic — DRY vs YAGNI~~ RESOLVED
Hickey and Martin both see duplicated flatten logic in adapter conversions. Both agree extraction would help. **Resolution: extract `_flatten_grid` when 3rd conversion function appears. Currently 2 functions — premature to extract.**
**Source:** Expert review #3

### D-09: ~~Registry abstraction — extract vs accept~~ RESOLVED
Martin: 5 identical registries (200 LOC) violate DRY; extract `Registry[T]`. Beck: current duplication is borderline; not worth abstracting until 6th registry. **Resolution: defer. 5 registries is borderline. Extract on 6th. See C-80.**
**Source:** Expert review #4

### D-10: ~~Config/discovery coupling — complecting vs fail-fast~~ RESOLVED
Hickey: `ViewpointConfig.__post_init__` validates strategy names by calling `get_survivorship()`, coupling config to module import side effects. Beck: simplest thing that works — fail fast at config time is better than deferred validation. **Resolution: Beck wins. Deferred validation moves errors further from the source.**
**Source:** Expert review #4

### D-11: ~~Schema evolution — registry vs YAGNI~~ RESOLVED
Kleppmann: needs schema registry and versioning. Beck: YAGNI until UCDP actually removes a field. **Resolution: Beck wins for now. Added schema fingerprint to ledger (C-69) as low-cost insurance. Full registry deferred per C-45/C-61.**
**Source:** Expert review #4

### D-12: ~~File lock timeout — simplicity vs operability~~ RESOLVED
Hickey: advisory lock is simple; adding timeout adds complexity. Nygard: indefinite block is unacceptable in production. **Resolution: Nygard wins. Added staleness check to `file_lock()` (C-68). Cheap insurance against operator-hours debugging hangs.**
**Source:** Expert review #4

### D-13: ~~FeatureFrame depth — thin wrapper vs deep module~~ RESOLVED
Ousterhout: too shallow, leaks grid conventions. Beck: it's a data wrapper, intentionally thin. **Resolution: both right. Added shape assertion in `from_grid()`. Don't deepen the abstraction beyond validation.**
**Source:** Expert review #4

### D-14: ~~Decorator vs function-call registration~~ RESOLVED
GoF: registration patterns inconsistent (decorator in aggregation/survivorship vs explicit call in sources/consolidators/builders). Martin: standardize on one. Hickey: both work; consistency is a nice-to-have, not a blocker. **Resolution: accept inconsistency at current scale. Standardize when extracting `Registry[T]` (C-80).**
**Source:** Expert review #4

### D-15: ~~Harvest template extraction~~ RESOLVED
GoF: the config->fetch->validate->compare->archive->store->provenance pattern should be a shared template. Beck: 3 implementations don't justify extraction yet. **Resolution: defer per C-44. Extract `HarvestPipeline` on 4th source.**
**Source:** Expert review #4

### D-16: ~~Parquet read seam for test speed~~ RESOLVED
Feathers: inject `read_table_fn` for faster unit tests. Beck: tests use real Parquet with tiny data; test suite runs in <5s. **Resolution: defer per C-79. Add seam when tests exceed 30 seconds.**
**Source:** Expert review #4

### D-17: ~~Consolidated store: append-only vs replace~~ RESOLVED
Kleppmann: store should be append-only for safety. Hickey: idempotent replace is simpler and correct. **Resolution: Hickey wins on semantics (replace is idempotent), Kleppmann wins on crash safety. Added atomic write via temp file + rename (C-67).**
**Source:** Expert review #4
