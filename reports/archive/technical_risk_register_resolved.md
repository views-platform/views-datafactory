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

### C-30: ~~No performance test for full-scale compilation~~ RESOLVED
Added `tests/test_performance.py` with `@pytest.mark.slow`. Compiles 50 events onto the full 360x720 PRIO-GRID (259,200 cells x 12 months) and asserts <60s. Runs in ~0.3s.
**Source:** Repo assimilation, Nygard. Resolved 2026-04-04.

### C-61: ~~No schema evolution test~~ RESOLVED
Added `tests/test_schema_evolution.py` with 4 tests: column added in later version (nulls in old rows), column removed in later version (nulls in new rows), mixed schemas across all 3 streams, and schema fingerprint change detection.
**Source:** Kleppmann (test review). Resolved 2026-04-04.

### C-89: ~~No formal SLO for data freshness~~ RESOLVED
`check_health.py` now defines `FRESHNESS_SLO_HOURS = 168` (7 days, per ADR-018) as a named constant. Export freshness is checked against the zarr `export_timestamp` attr and reported in both human and `--json` output. `verify_remote.py` check 5 now computes and displays export age, warning on SLO breach. Consumers can programmatically verify freshness via `check_health.py --json | jq .export_slo_met`.
**Source:** DDIA Ch.1 pp.13-14, Ch.2 pp.41-42, Ch.8 pp.237-240. Resolved 2026-04-06.

### C-103: ~~Feature name uniqueness not enforced in CompilationConfig~~ RESOLVED
Added uniqueness check in `CompilationConfig.__post_init__`: duplicate feature names now raise `ValueError` at config construction time, preventing silent data loss in zarr export. Test added in `test_compiler.py`.
**Source:** Repo assimilation 2026-04-04 (Phase 5, invariant 16). Resolved 2026-04-06.

### C-110: ~~Strategic doc test/concern counts drift across commits~~ RESOLVED
Updated `rd_roadmap04.md` and `product_development_plan03.md` to current state (411 tests, 111 concern IDs, 72 resolved, 31 open/deferred, 6 accepted by design).
**Source:** PR #6 review 2026-04-06. Resolved 2026-04-06.

### C-111: ~~Typo in test class name~~ RESOLVED
`TestXarrayConstruction` docstring corrected in `test_export_zarr_logic.py`. Class name kept as-is (spelling was actually correct — the 'c' is present; the review finding was a false positive).
**Source:** PR #6 review 2026-04-06. Resolved 2026-04-06.

### C-98: ~~No deployment gate~~ RESOLVED
`refresh_pipeline.sh` now reads a deploy tag from `~/.views-deploy-tag`, fetches tags, and checks out the specified tag before running the pipeline. If the file is missing, empty, or the tag doesn't exist, the script exits non-zero (fail-loud per ADR-011). Operators control deployments by writing a tag name to the file. Rollback: write the previous tag. See **ADR-022** for the full design rationale and alternatives considered.
**Source:** Falsification audit 2026-04-01 (F5). Resolved 2026-04-06.

### C-102: ~~No tests for assembly, zarr export, or dataframe export scripts~~ RESOLVED
Added 3 test files (22 tests): `test_assemble.py` (GID lookup bijection, spatial join, admin fill values, feature concatenation, mmap round-trip), `test_export_zarr_logic.py` (coordinate boundaries, xarray construction, zarr round-trip, metadata consolidation), `test_export_dataframe_logic.py` (sparse vs dense modes, month_id epoch encoding, empty grid handling).
**Source:** Repo assimilation 2026-04-04. Resolved 2026-04-06.

### C-80: ~~Registry boilerplate duplicated 6x~~ RESOLVED
Extracted generic `Registry[T]` class to `datafactory_provenance/registry.py`. All 6 registries (sources, consolidators, builders, aggregation, survivorship, temporal_distribution) now use `Registry` instances. Public APIs preserved via aliasing (`register_source = _registry.register`, `STRATEGIES = _registry.entries`). Test fixture `_clean_source_registry` continues to work via dict aliasing. 46 source files pass mypy strict.
**Source:** Martin (expert review #4). Resolved 2026-04-05.

### C-92: ~~Duplicated retry-delay logic in `datafactory_http`~~ RESOLVED
Extracted `_retry_or_raise()` helper in `retry.py`. Both the `HTTPError` and `RequestException` branches now call the shared function for retry-delay-or-raise logic. File reduced from 97 to 82 lines.
**Source:** PR #2 code review 2026-03-30. Resolved 2026-04-04.

### C-101: ~~3x duplicated min/max date code with type: ignore~~ RESOLVED
`ucdp_annual.py:295`, `ucdp_candidate.py:286`, and `ucdp_dot9.py:301` each had identical 6-line blocks extracting min/max date strings from event lists with `# type: ignore[type-var]`. Extracted `date_range()` helper to `event_validation.py` — returns typed `tuple[str | None, str | None]`, eliminates all 3 type ignores.
**Source:** Tech debt cleanup 2026-04-02

### C-60: ~~Health check logic untested~~ RESOLVED
Added 17 tests in `tests/test_check_health.py` covering `_read_last_entries` (normal, empty, missing, corrupt), `_report_ledger` (OK, STALE, FAILING, NO DATA), and `_check_export_freshness` (SLO met, breached, missing zarr, corrupt attrs).
**Source:** Nygard (test review), repo assimilation 2026-04-04. Resolved 2026-04-07.

### C-104: ~~Date string format assumed YYYY-MM-DD~~ RESOLVED
Added strict `_validate_date_str()` with regex `^\d{4}-\d{2}-\d{2}$` to `temporal_distribution.py` and `grid_compilation.py`. Rejects ISO datetime, slash format, missing leading zeros. 6 tests added.
**Source:** Repo assimilation 2026-04-04. Resolved 2026-04-07.

### C-105: ~~Assembly mmap write is not atomic~~ RESOLVED
`assemble_grid.py` now writes to `grid.npy.tmp` then `os.rename()` on success. Pre-flight disk space check via `shutil.disk_usage()`. Try/finally cleanup of `.tmp` on failure. 2 tests added.
**Source:** Repo assimilation 2026-04-04. Resolved 2026-04-07. DDIA Ch.7 pp.223-226, Ch.10 p.413.

### C-106: ~~Version parsing assumes dotted-integer format~~ RESOLVED
`survivorship.py:_parse_version()` now catches `ValueError` and returns `(0,)` with a warning. Non-numeric versions sort below all numeric ones — never preferred in survivorship. 7 tests added.
**Source:** Repo assimilation 2026-04-04. Resolved 2026-04-07.

### C-112: ~~Duplicate dimensionality validation across adapter files~~ RESOLVED
Extracted `validate_grid_pgids()` and `validate_pgids()` into `datafactory_adapters/_validation.py`. Three call sites now use the shared helpers. 4 tests added.
**Source:** Tech debt cleanup 2026-04-06. Resolved 2026-04-07.

### C-113: ~~Inconsistent HTTP timeout values~~ RESOLVED
Documented timeout policy in ADR-018 (per-payload-size tiers). Added inline comments to all 6 config classes referencing ADR-018. Actual values: UCDP 30s, PRIO-GRID static 60s, shapefile 120s, GAUL 300s, land mask 60s.
**Source:** Tech debt cleanup 2026-04-06. Resolved 2026-04-07.

### C-85: ~~Personal GitHub SSH key on shared server~~ RESOLVED
Generated ED25519 deploy key as `views-deploy` user. Registered on GitHub as read-only deploy key scoped to `views-platform/views-datafactory`. Personal key (`/root/.ssh/id_ed25519`) removed from server. `git fetch --tags` works as `views-deploy`. `verify_server_hardening.py` check 20 passes (personal key removed) and check 21 passes (deploy key exists).
**Source:** PRIO IT security guidance, executed 2026-04-09

### C-86: ~~No deploy key — repo access tied to personal account~~ RESOLVED
Deploy key registered on GitHub repo settings (title: `views-datafactory-00 (views-deploy)`, read-only, no write access). Org deploy key policy enabled at `views-platform` org level. Key is scoped to this single repo — cannot access any other repository in the org or on Simon's personal account.
**Source:** PRIO IT security guidance, executed 2026-04-09

### C-84: ~~Server runs everything as root~~ RESOLVED
Created `views-deploy` service account (uid=1000) on Hetzner server. Pipeline repository (code + 26 GB data) migrated from `/root/` to `/home/views-deploy/`. Cron job migrated from root to `views-deploy`. Symlinks in `/srv/views-data/` updated to new paths. Caddy traversal permission set (`chmod o+x /home/views-deploy`). Account has no sudo, no password, cannot install packages or modify system config. `verify_server_hardening.py` passes 19/21 (2 remaining are Phase 6.2 — deploy key). `verify_remote.py` passes 10/10 (data serving unaffected). Deployment guide Phase 6.1 rewritten with verbose what/why/how/permission-model/rollback documentation.
**Source:** PRIO IT security guidance, executed 2026-04-09

### C-114: ~~`source_aware` distribution strategy was opaque routing~~ RESOLVED
The `source_aware` strategy hardcoded routing logic (annual → date_end_only, everything else → ceil_split) inside a strategy function, making it invisible to config inspection. A researcher reading `distribution_strategy="source_aware"` had no way to know the routing without reading source code. Replaced by `source_distribution_map` config field on ViewpointConfig that makes the routing explicit and configurable. The `source_aware` strategy is deprecated (emits DeprecationWarning) but not removed. Production parity profile now declares `distribution_strategy="ceil_split", source_distribution_map={"annual": "date_end_only"}`.
**Source:** Parity investigation 2026-04-08. Resolved 2026-04-08.

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

### D-18: ~~Remote zarr: full materialization vs lazy subsetting~~ RESOLVED
Kleppmann: subset before materializing (1.8 GB download for 12 MB query is unacceptable). Beck: simplest thing that works first. **Resolution: Kleppmann wins — `_load_grid_from_zarr` now accepts `time_sel` and `feature_sel` hints, applied to xarray Dataset before `.values`. Remote smoke test loads 2 features x 12 months in 1.6s instead of full grid.**
**Source:** Expert review #5 (M12 investigation), 2026-04-08

### D-19: ~~Remote zarr: error information hiding vs operator visibility~~ RESOLVED
Ousterhout: deep module should hide error details. Nygard: operators need to distinguish auth/network/format failures. **Resolution: Nygard wins — 401 errors now raise `PermissionError` with "check ~/.netrc" message; netrc lookup failures log a warning; other network errors include the exception type and message. Generic `FileNotFoundError` only for genuinely missing stores.**
**Source:** Expert review #5 (M12 investigation), 2026-04-08

### C-118: ~~Zarr feature subsetting silently drops unknown features~~ RESOLVED
Added feature validation in `_load_grid_from_zarr` (`dataset.py:159-167`): checks requested features against available features before subsetting, raises `ValueError` with list of missing features. Now matches npy path behavior (`_resolve_feature_indices`). TDD: failing test written first, then fix applied. 512 tests pass.
**Source:** Expert review #6 (consumer API), Kleppmann + Beck. Resolved 2026-04-09.

### C-87: ~~No named user accounts on server~~ RESOLVED
Created `sonja_prio` account on Hetzner server: uid=1001, in sudo group, SSH key installed, password set via temp+chage flow (user changed it on first login). `passwd -S sonja_prio` returns `P 2026-04-10`. Sonja verified: SSH login works, sudo whoami returns root.

**Incident note:** First execution of Phase 6.3 surfaced a documentation gap — the original procedure created accounts with `useradd -m` (no password), which leaves the account locked (`passwd -S` shows `L`). SSH key login worked but `sudo` failed with "no password set". Fix: temp password generation with `openssl rand`, set via `chpasswd`, force change via `chage -d 0`, deliver via Slack DM. Phase 6.3 rewritten to verbose what/why/how/cannot-do/permission-model standard matching Phase 6.1/6.2. `verify_server_hardening.py` extended with named-account check that catches this exact failure mode. New concern C-121 registered to track unexecuted Phase 6.4.

**Source:** PRIO IT security guidance, executed 2026-04-10

### C-119: ~~`generate_consumer_data.py` has zero tests~~ RESOLVED
Added `tests/test_consumer_data.py` with 11 tests covering: correct columns, index names, feature rename, row/col derivation, NaN filling, sorted index, partition boundary matching (calibration, validation, forecasting), and rename map completeness. Uses `importlib.util` to load the script as a module.
**Source:** Expert review #6 (consumer API), Feathers + Beck. Resolved 2026-04-09.

### C-108: ~~Parquet and zarr exports serve different feature sets~~ RESOLVED
Documented the intentional asymmetry in `docs/guides/consumer_data_guide.md`: zarr has 43 features (full grid), parquet has 6 (UCDP conflict only). Table with endpoints, feature counts, source paths, and use cases.
**Source:** Repo assimilation 2026-04-04. Resolved 2026-04-09.

### C-91: ~~No pipeline duration tracking~~ RESOLVED
Added pipeline-level duration tracking to `refresh_pipeline.sh`. Records `duration_seconds`, `deploy_tag`, start/end timestamps to `logs/pipeline_duration.json` on each successful run. Per-step timing already existed in stdout; this adds machine-readable end-to-end tracking.
**Source:** DDIA Ch.1 p.13, Ch.8 pp.281-283. Resolved 2026-04-09.

### C-120: ~~Magic number 259,201 in regions.py~~ RESOLVED
Replaced `set(range(1, 259_201))` with `set(range(1, DEFAULT_GRID_CONFIG.n_cells + 1))` in `regions.py:184`. The global region cell count now derives from GridConfig instead of being hardcoded.
**Source:** Expert review #6 (consumer API), Nygard. Resolved 2026-04-09.

### D-20: ~~Should generate_partition be a library function or stay as a script?~~ RESOLVED
Ousterhout: make it importable from `datafactory_query` — saves consumers from reimplementing the rename/derive/fill pipeline. Hickey: scripts are fine; don't complect the library with consumer-specific transforms. **Resolution: Ousterhout wins — expose when a second consumer needs it. Currently one script; monitor.**
**Source:** Expert review #6 (consumer API), 2026-04-09

### D-21: ~~Should _load_grid be public?~~ RESOLVED
Hickey: expose for advanced consumers who want raw arrays. Martin: fewer entry points, simpler contract. **Resolution: defer — no consumer has asked for raw arrays yet. Expose when needed.**
**Source:** Expert review #6 (consumer API), 2026-04-09

### D-22: ~~Should the consumer contract (FEATURE_RENAME, PARTITIONS) be in a module or a script?~~ RESOLVED
GoF: extract to `datafactory_query.consumer_contract` for reuse. Beck: test the script directly, don't create modules for one-use code. **Resolution: GoF wins if a second consumer needs the same transforms. Beck wins today. Monitor.**
**Source:** Expert review #6 (consumer API), 2026-04-09

### C-122: Consumer model has no runtime data fetch from Hetzner — RESOLVED
~~bright_starship in views-models has no code path to obtain data from the datafactory at runtime.~~ **Resolved 2026-04-19:** `main.py` now calls `_ensure_data()` before HydranetManager starts. If `data/raw/{run_type}_viewser_df.parquet` is missing, `config_queryset.fetch_data()` calls `load_dataset()` from the Hetzner zarr store, renames columns to VIEWSER convention, derives row/col, and saves the parquet. `requirements.txt` includes `views-datafactory`. Cross-ref: C-116 (no retry on remote zarr), C-117 (spatial over-fetch).
**Source:** Consumer integration review 2026-04-19. Work package: Consumer integration.

### C-123: `africa_me_legacy` region file not distributed — RESOLVED
~~`africa_me_legacy_pgids.json` exists only in the developer's local `data/raw/gaul_admin/`.~~ **Resolved 2026-04-19:** The 13,110 pgids are now bundled as `africa_me_legacy_pgids.json` inside the `datafactory_query` package (`src/datafactory_query/`). `_load_legacy_pgids()` reads from `Path(__file__).parent`, not from `gaul_dir`. Any `pip install views-datafactory` includes the file. Cross-ref: C-122.
**Source:** Consumer integration review 2026-04-19. Work package: Consumer integration.

### C-124: No consumer onboarding for remote zarr credentials — RESOLVED
~~No documentation in views-models explains the `~/.netrc` requirement.~~ **Resolved 2026-04-19:** bright_starship's `README.md` now includes a Prerequisites section with `~/.netrc` setup instructions (machine, login, password format, chmod 600). Cross-ref: C-96 (fsspec netrc), C-97 (auth scalability).
**Source:** Consumer integration review 2026-04-19. Work package: Consumer integration.

### C-134: `get_last_valid_month_id()` silently returns None on all errors — RESOLVED
~~Broad `except Exception` swallowed network/auth/timeout/JSON errors into `None`.~~ **Resolved 2026-04-27:** Replaced with specific `except (URLError, HTTPError, TimeoutError)` that logs at ERROR and re-raises. `json.loads` moved outside try-except. `None` only returned when attribute legitimately absent. 4 tests added.
**Source:** Tech-debt-cleanup audit 2026-04-22. Work package: Data boundary safety chain.

### C-127: Zarr backend returns features in different order than npy backend — RESOLVED
~~Silent `sorted(data_vars)` fallback caused feature order divergence.~~ **Resolved 2026-04-27:** `_load_grid_from_zarr()` now emits `UserWarning` on fallback. `export_zarr.py` already writes `feature_order`. 2 tests added.
**Source:** Verification examples suite (M13) 2026-04-21. Work package: Query correctness.

### C-128: Scripts infer grid shape from arrays without config validation — RESOLVED
~~Shape unpacking preceded `assert_grid_shape()` in assemble_grid.py and export_dataframe.py.~~ **Resolved 2026-04-27:** Swapped order so validation gates unpacking (matching compile_grid.py which was already correct). 3 structural tests added.
**Source:** Magic-values compliance audit 2026-04-21. Work package: ADR-003 compliance.

### C-31: Candidate source depends on annual source — RESOLVED
~~candidate and .9 imported shared symbols from ucdp_annual, creating tight coupling.~~ **Resolved 2026-04-27:** Extracted `_ucdp_common.py` with `ENVELOPE_KEYS`, `UCDP_GED_API_BASE`, `validate_envelope()`. Discovery functions now call `validate_envelope()` and use `data["TotalCount"]` instead of `.get("TotalCount", 0)`. 2 envelope rejection tests added.
**Source:** Martin (expert review 5), magic-values audit 2026-04-21. Work package: Code cleanup.

### Tier 1 — Resolved (batch 2026-05-22)

### ~~C-165: GHS-POP viewpoint OOM — 22 GB peak on 8 GB server~~ — RESOLVED
**Resolved 2026-05-20.** Multi-phase fix across v1.2.15–v1.2.18: (a) strip-based aggregation replaced full-globe array allocation (v1.2.16); (b) removed float64→float32 whole-array conversion, deferred to per-strip conversion (v1.2.17); (c) `del` Python lists after Arrow creation, `maxworkers=1` on tifffile, unconditional strip aggregation (v1.2.18, see C-170/C-171/C-172). Peak RSS reduced from 22.1 GB to ~1.5 GB for viewpoint output, ~7.4 GB during GeoTIFF load (irreducible). Falsification test `test_align_to_globe_does_not_upcast_input` now passes.
**Source:** Falsification audit (2026-05-19), probe F2. Cross-ref: C-170 (list accumulation), C-171 (compilation), C-172 (latent branch), C-173 (no swap).

### ~~C-170: GHS-POP viewpoint list accumulation OOM (~6.5 GB Python objects)~~ — RESOLVED
**Resolved 2026-05-20.** `build_ghspop_v1` accumulated ~60M Python objects in three lists (`pgid_rows`, `month_id_rows`, `pop_count_rows`) that coexisted with the Arrow table during `pa.table()` creation. Peak: 7.4–8.3 GiB on a swapless 8 GiB server. Fixed by adding `del pgid_rows, month_id_rows, pop_count_rows` after Arrow table creation. Additionally, `page.asarray(maxworkers=1)` reduces tifffile decompression buffering by ~400 MB, and the `needs_align` branching was removed so `build_ghspop_v1` always uses `_aggregate_with_alignment` (eliminating the latent OOM in `_aggregate_to_prio_grid`'s `data.copy()`). Falsification tests `test_lists_deleted_before_digest`, `test_read_geotiff_limits_decompression_threads`, `test_build_always_uses_strip_aggregation` now pass.
**Source:** Falsification audit + 8-expert code review (2026-05-20). Cross-ref: C-165 (original OOM), C-171 (compilation variant), C-172 (latent branch OOM).

### ~~C-171: Pregridded compilation `.to_pylist()` OOM (~6 GB Python objects)~~ — RESOLVED
**Resolved 2026-05-20.** `compile_pregridded` called `.to_pylist()` three times on Arrow columns, inflating ~60M rows into ~6 GB of Python objects alongside the Arrow table (~1 GB) and grid array (~0.5 GB). Peak: ~7.7 GiB. Fixed by replacing `.to_pylist()` with `.to_numpy()` and adding `del table` after extraction. Null guard updated from `val is not None` to `not np.isnan(val)` for numpy compatibility. Falsification test `test_compilation_avoids_to_pylist` now passes.
**Source:** Falsification audit + 8-expert code review (2026-05-20). Cross-ref: C-144 (same pattern in `grid_compilation.py`, still deferred), C-170 (viewpoint variant).

### ~~C-172: Latent OOM in `_aggregate_to_prio_grid` dead branch~~ — RESOLVED
**Resolved 2026-05-20.** `build_ghspop_v1` had a `needs_align` branch that called `_aggregate_to_prio_grid` when raster dimensions were divisible by 60. That function does `data.copy()` — doubling a 6.88 GiB float64 array to 13.76 GiB peak. The only protection was JRC's accidental non-divisible-by-60 raster dimensions (21384×43202). Fixed by removing the branching and always using `_aggregate_with_alignment` (which handles both aligned and unaligned data via offset computation). `_aggregate_to_prio_grid` and `_align_to_globe` retained as module-level functions (tested directly in 7 existing tests). Falsification test `test_build_always_uses_strip_aggregation` now passes.
**Source:** Falsification audit + 8-expert code review (2026-05-20). Cross-ref: C-163 (dimension truncation, resolved), C-170 (main memory fix).

### ~~C-162: GHS-POP PGID mapping has no direct correctness test~~ — RESOLVED
**Resolved 2026-05-19.** Added `test_pgid_mapping_correctness` (4 distinct populations in 2x2 grid, asserts specific pgid→value mapping including row-flip), `test_month_id_correctness` (verifies Jan/Feb/Mar 2000 → month_ids 241/242/243), and `test_no_duplicate_pgid_month_id` (uniqueness constraint on output). Test count: 21 → 29.
**Source:** GHS-POP viewpoint test review (2026-05-19). Cross-ref: C-149 (GAUL unmapped cells).

### Tier 2 — Resolved (batch 2026-05-22)

### ~~C-166: GHS-POP absent from PIPELINE_SOURCES — verify_remote.py blind~~ — RESOLVED
**Resolved 2026-05-20.** Added three `SourceEntry` entries to `PIPELINE_SOURCES`: `"GHS-POP"` (harvest, `features=("ghspop_pop_count",)`, `slo_hours=None`, ledger at `ghspop/ingestion_ledger.jsonl`), `"GHS-POP Viewpoint"` (ledger at `viewpoint/ghspop_v1_ledger.jsonl`), `"GHS-POP Compilation"` (ledger at `compilation/ghspop_ledger.jsonl`). `get_all_features()` now returns 52 features (was 51). Falsification tests `test_ghspop_feature_in_registry` and `test_ghspop_source_entry_exists` now pass. Feature count test updated from 51 to 52.
**Source:** Falsification audit (2026-05-19), probe F1. Cross-ref: C-138 (post-deploy verification), C-132 (health check gap).

### ~~C-163: `_aggregate_to_prio_grid` silently truncates non-divisible raster dimensions~~ — RESOLVED
**Resolved 2026-05-19.** Added dimension validation (`nrow % 60 != 0 or ncol % 60 != 0` → `ValueError`) to `_aggregate_to_prio_grid`. Added `test_non_divisible_dimensions_raises` to verify the guard. Also added: `test_no_args_raises`, `test_unknown_epoch_raises`, `test_all_zero_raster_produces_empty_output`, `test_source_dir_shortcut`.
**Source:** GHS-POP viewpoint test review (2026-05-19). Cross-ref: C-162 (PGID mapping correctness).

### ~~C-182: `last_digest_for_version` returns digest from failed ledger entries~~ — RESOLVED
**Resolved 2026-05-21.** `last_digest_for_version` now skips entries where `outcome` is present and not `"success"`. Entries without an `outcome` field are accepted for backward compatibility with pre-outcome ledger entries. Added 3 tests: `test_skips_failed_entries`, `test_returns_none_when_only_failed`, `test_accepts_entries_without_outcome`.
**Source:** Expert code review of harvest caching (2026-05-21). Cross-ref: C-184 (ACLED no file integrity check), C-185 (GHS-POP no digest comparison), C-46 (ledger write idempotency).

### ~~C-150: Zero Red team tests for ACLED pipeline~~ — RESOLVED
**Resolved 2026-05-02.** Added `TestFetchAcledRed` (5 tests), `TestConsolidateAcledRed` (4 tests), `TestBuildAcledV1Red` (4 tests) covering: token endpoint garbage, missing `expires_in` fallback, non-list API data, missing required fields, frozen mutation, malformed filenames, corrupted Parquet, schema drift, malformed event dates, total filter elimination, missing store columns.
**Source:** ACLED integration test review (2026-05-02). Cross-ref: C-72 (HTTP 429 not distinguished), C-45 (no schema evolution strategy).

### ~~C-140: v1.2.6/v1.2.7 incident fixes have zero test coverage~~ — RESOLVED
**Resolved 2026-04-26.** Added 7 tests: `TestTotalCountAssertionBeige` (4 tests: tolerance pass, truncation raises, exact boundary, max_pages skip) and `TestRateLimitBackoffRed` (3 tests: HTTP 400 retry with backoff, exhaustion raises, non-400 bypass). Also added `TestValidateEnvelopeRed` (3 tests) and `TestUcdpAnnualRegistration` (1 test).
**Source:** Test review 2026-04-26. Cross-ref: C-137, C-138, C-139 (data integrity).

### Tier 3 — Resolved (batch 2026-05-22)

### ~~C-141: UCDP config class validation partially untested~~ — RESOLVED
**Resolved 2026-04-26.** Added 8 Beige tests across three config classes: `UcdpAnnualConfig` (page_delay, timeout), `UcdpCandidateConfig` (page_size, max_retries, timeout), `UcdpDot9Config` (page_size, max_retries, timeout). All CIC-guaranteed fail-loud branches now tested.
**Source:** Test review 2026-04-26. Cross-ref: C-31, C-07.

### ~~C-142: datafactory_query consumer entry point has zero Red/Beige tests~~ — RESOLVED
**Resolved 2026-04-26.** Added `TestLoadDatasetBeige` (2 tests: single-feature request, explicit-matches-default) and `TestLoadDatasetRed` (5 tests: corrupted grid, mismatched feature count, mismatched pgids shape, NaN-filled grid, zero time steps).
**Source:** Test review 2026-04-26. Cross-ref: C-127, C-130.

### ~~C-151: No CICs for ACLED config classes~~ — RESOLVED
**Resolved 2026-05-02.** Created `docs/CICs/AcledConfig.md`, `docs/CICs/AcledConsolidationConfig.md`, `docs/CICs/AcledViewpointConfig.md` following the 11-section template. Frozen-enforcement tests added for all three configs.
**Source:** ACLED integration test review (2026-05-02). Cross-ref: C-07 (frozen dataclass pattern repeated), C-150 (zero Red tests).

### ~~C-152: ACLED profiles and `list_acled_profiles()` untested~~ — RESOLVED
**Resolved 2026-05-02.** Added `TestAcledProfilesGreen` (4 tests: `load_acled_violence_only`, `load_acled_all_events`, `load_with_override`, `list_acled_profiles`) and `TestAcledProfilesRed` (1 test: `unknown_acled_profile_raises`) in `tests/test_acled_viewpoint.py`.
**Source:** ACLED integration test review (2026-05-02). Cross-ref: C-150 (ACLED test gaps).

### ~~C-157: Systematic ACLED documentation drift across ADRs, CICs, and guides — [RESOLVED 2026-05-07]~~

| Field | Value |
|-------|-------|
| ID | C-157 |
| Tier | 3 |
| Source | base documentation review (2026-05-07) |
| Trigger | New team member (Dylan, Sonaj) reads stale documentation and builds on wrong assumptions about feature counts, pipeline steps, or ACLED integration status |
| Location | ADR-028 (critical: says compiler doesn't exist), ADR-009, ADR-021 (high: wrong counts), ADR-003/011/012/018/022 (medium), consumer_data_guide.md, zarr_consumer_guide.md (consumer-facing), plus 7 low-severity items |

ACLED integration completed across harvester, consolidation, viewpoint, compilation, and assembly — but ~15 documents still reference ACLED as hypothetical or future work. Three concrete harms: (1) ADR-028 Implementation Notes say "ACLED compiler does not exist yet" while it runs in production as pipeline step 5; a developer could re-implement it. (2) Consumer-facing guides (consumer_data_guide.md, zarr_consumer_guide.md) say "43 features" — consumers write code expecting 43 and get 51. (3) zarr_consumer_guide.md has `petroleum_y` typo (correct name: `petroleum_s`) which would cause `KeyError` for consumers. Additional drift: ADR-009 says "seven packages" (now 10), ADR-022 says "7 pipeline steps" (now 9), ADR-018 omits ACLED from SLO tables.

Cross-ref: C-158 (missing CICs).

### Tier 4 — Resolved (batch 2026-05-22)

### ~~C-143: request_with_retry has no Red tests~~ — RESOLVED
**Resolved 2026-04-26.** Added `TestRequestWithRetryRed` (2 tests: `requests.Timeout` retried, `HTTPError` with `response=None` retried not treated as 4xx).
**Source:** Test review 2026-04-26. Cross-ref: C-70, C-72.

### ~~C-125: No country-month (cm) aggregation — 48/70 models cannot migrate~~ — [RESOLVED]
Resolved 2026-04-21. `load_dataset(output_format="country_month")` now aggregates grid cells by country per month using `gaul0_code` as the grouping key. Adapter: `grid_to_country_month()` in `datafactory_adapters`. Active conflict features (ged_sb/ns/os_best) summed per (month_id, country_id). WDI/V-DEM/topic features remain out of scope (C-126 covers the transform gap).
**Source:** Falsification audit 2026-04-20 (F3). Cross-ref: S1 in `test_falsification_viewser_replacement.py`.

### ~~C-158: No CICs for SourceEntry or AssemblyConfig — [RESOLVED 2026-05-07]~~

| Field | Value |
|-------|-------|
| ID | C-158 |
| Tier | 4 |
| Source | base documentation review (2026-05-07), CIC audit |
| Trigger | Developer modifies SourceEntry fields or AssemblyConfig validation without understanding the contract — e.g., removing a `__post_init__` check that 5 consumers depend on |
| Location | `src/datafactory_provenance/source_registry.py:28` (SourceEntry), `scripts/assemble_grid.py:36` (AssemblyConfig) |

Two frozen dataclasses with `__post_init__` validation lack CICs. `SourceEntry` is the backbone of the source registry — health checks, pre-flight validation, assembly, and remote verification all import from it. `AssemblyConfig` governs grid assembly with validated defaults. Both follow the ADR-009 boundary contract pattern. Analogous to resolved C-151 (ACLED config CICs) but for different classes. Also noted: `SpatioTemporalGrid` CIC has medium drift — documents `pgids`/`lats`/`lons` as 1-D arrays but they are actually 2-D `[H, W]`.

Cross-ref: C-157 (documentation drift), C-151 (resolved, ACLED CICs).

### ~~C-161: GHS-POP harvester failure-path provenance partially untested~~ — RESOLVED
**Resolved 2026-05-18.** Added 3 tests and strengthened 2 existing tests: `test_corrupt_zip_raises_and_records_ledger` (verifies both exception and failure ledger entry), `test_zip_with_no_tif_raises` (valid ZIP with no .tif), `test_rejects_negative_timeout`, `test_empty_epochs_accepted`. Strengthened `test_download_single_epoch` (content round-trip: `read_bytes() == b"fake geotiff data"`), `test_provenance_recorded` (digest correctness: computed digest matches ledger entry), `test_defaults` (asserts `ledger_path` default). Test count: 15 → 18.
**Source:** GHS-POP harvester test review (2026-05-18). Cross-ref: C-44 (harvest pipeline template).

### ~~C-167: reports/audit_ghspop/ not in .gitignore~~ — RESOLVED
**Resolved 2026-05-20.** Added `reports/audit_ghspop/` to `.gitignore` alongside `reports/audit_acled/`.
**Source:** Falsification audit (2026-05-19), probe F5. Cross-ref: C-155 (visual audit framework).

### ~~C-187: Digest-field assumption in reverse scan shadows valid entries~~ — RESOLVED

**Resolved 2026-05-21.** Both `last_digest` and `last_digest_for_version` now skip entries where `entry.get(digest_field)` is `None`, continuing the reverse scan to find a valid entry. Added digest-field guard: `digest = entry.get(digest_field); if digest is not None: return digest`. Falsification tests in `test_falsification_pr59_merge_r2.py` now pass.
**Source:** Falsification audit round 2 of PR #59 (2026-05-21). Cross-ref: C-182 (outcome filtering fix), C-46 (ledger write idempotency).

### ~~C-188: GAUL admin failure path writes no ledger entry~~ — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-188 |
| Tier | 3 |
| Source | Expert code review of provenance/shapefile (2026-05-21) |
| Trigger | GAUL admin variable write fails in production; operator queries ledger for failure history and finds no record |
| Location | `src/datafactory_harvester/sources/gaul_admin.py:550-558` |

**Resolved (v1.2.18):** Added `append_ledger_entry` call with `"outcome": "failed"` inside the existing except block. GAUL admin failures are now recorded in the provenance ledger with dataset, version, outcome, and error message. Test: `test_gaul_admin.py::TestGaulAdminFailureLedger::test_write_variable_failure_records_ledger_entry`.

Cross-ref: C-186 (shapefile harvester same gap, deferred), C-44 (harvest pipeline template), ADR-032.
