# Expert Review Concerns — Remaining Items

**Date:** 2026-03-17
**Source:** Multi-expert engineering review of views-datafactory
**Status:** Updated post-MVP. 11 of 23 concerns resolved. 4 of 4 disagreements resolved or evaluable.

---

## Architecture & Design

### C-01: No enforcement mechanism for the DAG beyond tests
ADR-002 declares strict import rules but the only enforcement is the import-enforcement test added in `tests/test_import_enforcement.py`. There is no linting rule (e.g., `import-linter` config) or pre-commit hook. A contributor who doesn't run tests locally can still merge violations.
**Source:** Martin, Feathers

### C-02: Dual version source
`pyproject.toml:3` declares `version = "0.1.0"` and `src/datafactory_core/__init__.py:8` declares `__version__ = "0.1.0"`. These can diverge silently. Consider `hatch-vcs` or dynamic version reading.
**Source:** Martin

### C-03: Protocol proliferation risk in synthetic module
`src/datafactory_synthetic/ARCHITECTURE.md` plans 3 Protocols (SpatialKernel, TemporalProcess, MagnitudeDistribution) before any concrete implementation exists. Premature abstraction — defer Protocols until a second implementation is needed.
**Source:** GoF, Hickey

### C-04: ~~No factory or registry for harvester sources~~ RESOLVED
Dict-based source registry implemented in `datafactory_harvester/sources/__init__.py` (DoD003). `fetch_source("ucdp_annual")` works. UCDP annual auto-registers on import.

### C-05: ~~SpatioTemporalGrid composition contract unclear~~ RESOLVED
Formal CIC created at `docs/CICs/SpatioTemporalGrid.md` (DoD002). Section 3 explicitly states delegation, not duplication.

### C-06: Provenance logic should be a composable utility, not distributed
ARCHITECTURE.md files specify every module must write provenance. This distributes the concern. A context manager or decorator in `datafactory_core` would be simpler.
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

### C-17: Revision storage semantics underspecified
When UCDP revises past months, does the system keep both snapshots or overwrite? `ComparisonResult` exists conceptually but storage semantics are undefined.
**Source:** Kleppmann

### C-18: Schema evolution of provenance ledgers unplanned
Ledger entries will need new fields as the system matures. No versioning scheme (e.g., `"ledger_schema_version": 1`) is defined for forward/backward compatibility.
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

## Expert Disagreements (Unresolved Tensions)

### D-01: Governance proportionality
Ousterhout and Hickey see the 10 ADRs + 5 ARCHITECTURE.md as disproportionate overhead for a 50-line codebase. Martin and the ADR structure argue this is insurance against future drift. **Resolution depends on whether the governance prevents real mistakes during migration.**

### D-02: ~~Early Protocols vs. YAGNI~~ RESOLVED
Built simplest thing first: aggregation strategies are plain functions, not Protocols. Validated by DoD004 — 3 strategies (count, sum_best, max_best) work without abstraction overhead. Extract Protocol when a second source needs different strategy signatures.

### D-03: Fail-loud vs. operational resilience
ADR-003/008 mandate fail-loud everywhere. Nygard asks what the operational experience is when the UCDP API is down for 3 days. **Resolution: define "stale data serving" policy as a project-specific ADR (010 candidate).**

### D-04: Tests-first vs. characterization-first
Beck says write specification tests now. Feathers says capture the metric lab's actual behavior first. **Both are valid; spec tests (now done) define the target, characterization tests (future) verify the migration.**
