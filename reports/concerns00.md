# Expert Review Concerns — Remaining Items

**Date:** 2026-03-17
**Source:** Multi-expert engineering review of views-datafactory
**Status:** Updated post-expert-review-5. 15 of 35 concerns resolved. 4 of 4 disagreements resolved.

---

## Architecture & Design

### C-01: No enforcement mechanism for the DAG beyond tests
ADR-002 declares strict import rules but the only enforcement is the import-enforcement test added in `tests/test_import_enforcement.py`. There is no linting rule (e.g., `import-linter` config) or pre-commit hook. A contributor who doesn't run tests locally can still merge violations.
**Source:** Martin, Feathers

### C-02: Dual version source
`pyproject.toml:3` declares `version = "0.1.0"` and `src/datafactory_provenance/__init__.py:8` declares `__version__ = "0.1.0"`. These can diverge silently. Consider `hatch-vcs` or dynamic version reading.
**Source:** Martin

### C-03: Protocol proliferation risk in synthetic module
`src/datafactory_synthetic/ARCHITECTURE.md` plans 3 Protocols (SpatialKernel, TemporalProcess, MagnitudeDistribution) before any concrete implementation exists. Premature abstraction — defer Protocols until a second implementation is needed.
**Source:** GoF, Hickey

### C-04: ~~No factory or registry for harvester sources~~ RESOLVED
Dict-based source registry implemented in `datafactory_harvester/sources/__init__.py` (DoD003). `fetch_source("ucdp_annual")` works. UCDP annual auto-registers on import.

### C-05: ~~SpatioTemporalGrid composition contract unclear~~ RESOLVED
Formal CIC created at `docs/CICs/SpatioTemporalGrid.md` (DoD002). Section 3 explicitly states delegation, not duplication.

### C-06: Provenance logic should be a composable utility, not distributed
ARCHITECTURE.md files specify every module must write provenance. This distributes the concern. A context manager or decorator in `datafactory_provenance` would be simpler.
**Source:** Hickey

### C-07: Frozen dataclass pattern repeated without shared base
GridConfig, TemporalConfig, HarvesterConfig, CompilationConfig, SyntheticConfig all follow the same frozen-dataclass-with-`__post_init__` pattern. No shared Protocol or base class captures this. Consider a `ValidatedConfig` Protocol in core.
**Source:** Hickey

---

## Documentation & Governance

### C-08: ~~Documentation complexity exceeds code complexity~~ RESOLVED
Ratio improved from ~7:1 (words per LOC) to ~3:1 as codebase grew to ~4,500 LOC. Governance has proven itself: ADR-008 caught bugs in 3 consecutive audits, ADR-002 enforced by import test, ADR-010 guided GridConfig redesign.

### C-09: ARCHITECTURE.md files duplicate ADR content
Each per-module ARCHITECTURE.md restates dependency rules from ADR-002, invariants from ADR-003, and boundary contracts from ADR-009. Changes to ADRs require updating 5 ARCHITECTURE.md files. Consider referencing ADRs by number rather than restating.
**Source:** Ousterhout

### C-10: Ontology vocabulary overhead
Terms like "Source Nodes," "Compilation Edges," "Explicit Non-Entities" are precise but add a conceptual layer every contributor must internalize. For a 5-package Python project, this may be heavy governance.
**Source:** Ousterhout

### C-11: Governance should prove itself
If an ADR hasn't prevented a mistake or resolved a disagreement within 3 months of active development, question whether it's load-bearing. Supersede or deprecate unused ADRs.
**Source:** Ousterhout, Hickey, long-term regret test

---

## Reliability & Operations

### C-12: ~~No retry policy or circuit breaker for UCDP API calls~~ RESOLVED
Exponential backoff (`2**attempt`) implemented in both `grid/harvester.py:_download` and `ucdp_annual.py:_request_with_retry`. Tested with mock retries.

### C-13: ~~No timeout declarations~~ RESOLVED
`timeout` configurable in `UcdpAnnualConfig` (default 30s) and `grid/harvester.py:fetch_shapefile` (default 120s). Passed through to `requests.get`.

### C-14: JSONL provenance files are unbounded
`provenance/harvester_ledger.jsonl` grows indefinitely. Over years of monthly harvesting this could become unwieldy. No rotation, compaction, or archival strategy is planned.
**Source:** Nygard

### C-15: No graceful degradation path
ADR-008 mandates fail-loud everywhere. No discussion of what happens operationally when a harvest fails: serve stale data with a warning, or block entirely? The operational response is undefined.
**Source:** Nygard

### C-16: No concurrency model
Simultaneous harvester runs could produce partial Parquet writes or interleaved JSONL appends. Neither ADRs nor ARCHITECTURE.md files address concurrent access. At minimum, document "single-writer, enforced by convention."
**Source:** Kleppmann

### C-17: ~~Revision storage semantics underspecified~~ PARTIALLY RESOLVED
`archive_snapshot` in `storage.py` renames old snapshots with UTC timestamps before overwriting. `ComparisonResult` tracks added/removed/revised events. Candidate monthly uses per-version snapshots. Full resolution: document archival retention policy.
**Source:** Kleppmann

### C-18: Schema evolution of provenance ledgers unplanned (deferred 6 times)
Ledger entries will need new fields as the system matures. No versioning scheme (e.g., `"ledger_schema_version": 1`) is defined for forward/backward compatibility. Deferred in DoD001, DoD002, DoD003, DoD004, DoD005, and expert review 5. Trivial fix (1 line per call site) with unbounded future value.
**Source:** Kleppmann

### C-19: ~~Deterministic compilation untested~~ RESOLVED
`test_compiler.py::test_deterministic` compiles same input twice and verifies identical output digests (DoD004).

### C-20: ~~Provenance ledger corruption on process kill~~ RESOLVED
`_read_ledger_entries` in `provenance.py` skips malformed trailing lines with a warning (DoD001). Tested by `test_malformed_trailing_line_skipped`.

---

## Testing

### C-21: No characterization tests for migration source
The metric lab code being migrated has its own tests, but this repo has no "golden output" tests that capture expected behavior of migrated code. Migration without characterization tests risks silent behavioral divergence.
**Source:** Feathers

### C-22: ~~No test structure for red/beige/green taxonomy~~ RESOLVED
Test categories organized by class naming convention (`TestXxxGreen`, `TestXxxBeige`, `TestXxxRed`). Documented in ADR-005 Implementation Convention section.

### C-23: `network` marker defined but unused
`pyproject.toml:50-51` declares the `network` marker but no test uses it. Dead configuration.
**Source:** Beck

---

## Performance & Scaling (from repo assimilation post-DoD005)

### C-24: Compiler loads entire Parquet into list-of-dicts
`compiler.py:161-163` converts Parquet columnar data to row-oriented `list[dict]` via `table.to_pydict()` + list comprehension. For 384K events × 49 fields this creates ~19M Python objects. Works at current scale; will not scale to millions of events.
**Source:** Repo assimilation, Kleppmann

### C-25: Source digest reads entire file into memory
`compiler.py:147` calls `config.source_path.read_bytes()` to compute SHA-256. For a 50MB Parquet file this doubles memory usage. Chunked hashing would be better.
**Source:** Repo assimilation, Nygard

### C-26: `_read_ledger_entries` reads entire JSONL file
`provenance.py:136` reads all lines to find the last entry. O(n) for every `last_digest` call. Fine for hundreds of entries; slow for thousands.
**Source:** Repo assimilation, Kleppmann

### C-27: Retry pattern duplicated in 2 modules
`grid/harvester.py:52-75` and `ucdp_annual.py:132-163` implement the same exponential backoff loop. Deferred per "third use" DRY rule — extract to core when a third module needs it.
**Source:** Repo assimilation, expert review 4

### C-28: Candidate source uses fake annual config workaround
`ucdp_candidate.py:188-198` constructs `UcdpAnnualConfig(start_year=2000, end_year=2099)` to reuse `fetch_paginated`. Sends unnecessary 100-year date range to API. Works correctly but is architecturally inelegant.
**Source:** Falsification audit DoD005 (observation P4)

### C-29: No end-to-end integration test
No test runs the full harvest → compile pipeline with real (or realistic) Parquet data. Individual modules are well-tested in isolation but the integration boundary is untested.
**Source:** Repo assimilation, Feathers

### C-30: No performance test for full-scale compilation
The 60-second performance target (NF-5: 259,200 cells × 432 months) has no test. Compilation is only tested with 8-cell synthetic grids. Full-scale behavior is unverified.
**Source:** Repo assimilation, Nygard

---

## Coupling & Typing (from expert review 5)

### C-31: Candidate source depends on annual source
`ucdp_candidate.py:25-31` imports 5 symbols from `ucdp_annual.py` including `UcdpAnnualConfig`. Changing annual's API client could break candidate. Extract `_ucdp_common.py` when a third shared function is needed.
**Source:** Martin (expert review 5)

### C-32: Source registry returns `Any` — no typed interface
`fetch_source` returns `Any` (widened from `Path` for candidate's `list[dict]`). Consumers can't rely on the return type without reading the source module. Accept for now; consider a `SourceResult` union if it causes real problems.
**Source:** GoF, Hickey (expert review 5)

### C-33: ~~Discovery probes had no rate limiting~~ RESOLVED
`discover_versions` fired rapid sequential HTTP requests. Fixed: added `time.sleep(0.5)` between probes.

### C-34: ~~Global mutable source registry — test pollution~~ RESOLVED
`_SOURCES` dict is module-level mutable state. Fixed: added `_clear_registry()` and conftest.py fixture that removes test-registered sources after each test.

### C-35: Digest algorithm not recorded in provenance entries
Entries contain `content_digest` but not the algorithm ("sha256") or truncation length (16). If the algorithm changes, old digests become incomparable. Fix: add `"digest_algorithm": "sha256_16"` to provenance entries.
**Source:** Kleppmann (expert review 5)

---

## Expert Disagreements (Unresolved Tensions)

### D-01: ~~Governance proportionality~~ RESOLVED
Governance has proven itself across 5 DoDs: ADR-008 caught bugs in 3 consecutive falsification audits, ADR-002 enforced by import test prevented coupling, ADR-010 guided GridConfig SRP redesign, ADR-003 motivated pgid bounds check and month validation. Docs-to-code ratio improved from 7:1 to ~2:1 as codebase grew to 2,674 LOC.

### D-02: ~~Early Protocols vs. YAGNI~~ RESOLVED
Built simplest thing first: aggregation strategies are plain functions, not Protocols. Validated by DoD004 — 3 strategies (count, sum_best, max_best) work without abstraction overhead. Extract Protocol when a second source needs different strategy signatures.

### D-03: Fail-loud vs. operational resilience
ADR-003/008 mandate fail-loud everywhere. Nygard asks what the operational experience is when the UCDP API is down for 3 days. **Resolution: define "stale data serving" policy as a project-specific ADR (010 candidate).**

### D-04: Tests-first vs. characterization-first
Beck says write specification tests now. Feathers says capture the metric lab's actual behavior first. **Both are valid; spec tests (now done) define the target, characterization tests (future) verify the migration.**
