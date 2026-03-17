
# ADR-008: Observability and Explicit Failure

**Status:** Accepted
**Date:** 2026-03-17
**Deciders:** Simon Polichinel von der Maase, Claude Code

---

## Context

views-datafactory produces compiled grid data whose values propagate into conflict forecasts used by humanitarian organizations. Silent failure, degraded semantics, or partial execution can cause cascading downstream impact that may not be detected until forecasts are already in use.

Stack traces alone are insufficient for traceability in a system with multiple independent data sources, filesystem-mediated coupling, and provenance ledgers that must remain complete.

To preserve architectural integrity and post-hoc auditability, failures must be both:

- **explicitly raised**, and
- **persistently recorded**.

The JSONL provenance ledgers (`provenance/`) are the primary observability mechanism for this system. Python logging at WARNING/ERROR/CRITICAL levels supplements but does not replace ledger entries.

---

## Decision

The repository adopts the following invariant:

> Structural failures must be both **logged persistently** and **raised explicitly**.

### 1. Explicit Failure

- Invariant violations must raise exceptions.
- Structural failures must not be downgraded to warnings.
- Errors must not be silently swallowed.
- Fallback behavior must not hide semantic failure.

Fail-loud (ADR-003) applies fully to runtime behavior.

Domain-specific fail-loud examples:

- Schema validation failure during harvest: must **raise**, not warn, if required UCDP fields are missing
- Digest mismatch at compilation time: must **raise**, not proceed with stale data
- Grid generation producing unexpected cell count: must **raise**, not silently truncate
- Provenance ledger append failure: must **raise**, not silently skip (provenance is mission-critical)
- Configuration with missing required fields: must **raise** in `__post_init__`, not substitute defaults
- Compiled output with shape mismatch: must **raise**, not reshape silently

---

### 2. Persistent Observability

- Raised structural failures must be logged at `ERROR` level or higher.
- Critical system-wide failures must be logged at `CRITICAL`.
- Logging must occur before or at the point of raising.
- Logging is not a substitute for raising; raising is not a substitute for logging.
- Provenance ledger entries must record validation results (including errors and warnings) for every operation, whether it succeeds or fails.

---

### 3. Scope

This ADR applies to:

- data validation failures (harvest-time schema checks, compilation input validation),
- configuration inconsistencies (`__post_init__` violations),
- semantic ambiguity (digest mismatches, version conflicts),
- broken invariants (wrong cell count, wrong array shape, missing coordinate arrays),
- provenance integrity failures (ledger corruption, missing entries),
- and other structural system failures.

It does not prescribe formatting, spacing, or specific logging utilities.
Operational conventions may evolve separately (see `standards/logging_and_observability_standard.md`).

---

## Consequences

### Positive

- Persistent traceability of structural failures
- Reduced debugging entropy
- Strong alignment with fail-loud invariant (ADR-003)
- Provenance ledgers serve as both audit trail and observability mechanism

### Negative

- Slight increase in boilerplate
- Requires discipline in error handling

These costs are accepted.

---

## Notes

This ADR defines architectural requirements for failure handling.

It does not define log formatting standards, log retention policies,
or logging infrastructure configuration, which are operational concerns.

Observability must support understanding.
Failure must never be silent.
