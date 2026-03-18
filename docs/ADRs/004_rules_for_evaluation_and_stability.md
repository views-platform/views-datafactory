
# ADR-004: Rules for Evolution and Stability

**Status:** Deferred
**Date:** 2026-03-17
**Deciders:** --
**Informed:** All contributors

---

## Context

The preceding ADRs establish:

- **ADR-001:** the ontology of the repository (what exists)
- **ADR-002:** the topology of the repository (how components may relate)
- **ADR-003:** semantic authority (who owns meaning and how it is declared)

Together, these decisions define the system's structure and semantics at a point in time.

What they do **not** yet define is how the system is allowed to **change over time**:
- which components are expected to be stable
- which components may evolve freely
- what constitutes a breaking change
- when compatibility guarantees apply
- when a new ADR is required

These questions are architectural, cross-cutting, and costly to reverse once external users or downstream dependencies exist.

---

## Decision

No decision is made at this time.

Rules governing stability, evolution, and backwards compatibility are **explicitly deferred**.

This ADR exists to:
- acknowledge the importance of this dimension
- reserve a place for a future, explicit decision
- prevent ad-hoc or implicit policies from emerging unnoticed

---

## Rationale for Deferral

At the time of writing:

- Core abstractions are being migrated from the metric lab and refined
- The boundary between experimental and stable components may shift
- Premature guarantees would either be ignored or constrain necessary exploration

Deferring this decision preserves design freedom while maintaining architectural honesty.

---

## Trigger Conditions for Reconsideration

This ADR should be revisited when one or more of the following become true:

- The metric lab adds `views-datafactory` to its `pyproject.toml` dependencies (import dependency, not just filesystem reads)
- views-hydranet or views-pipeline-core depend on `datafactory_priogrid` or `datafactory_compilation`
- Reproducibility across time becomes a contractual requirement (e.g., OCHA requires versioned data)
- The screaming architecture rename (c9d8cf9) causes downstream breakage — evidence that stability guarantees are needed
- Multiple versions of the same compiled grid must be supported concurrently
- Contributors express uncertainty about what is safe to change

**Governance audit note (2026-03-18):** Reviewed post-DoD005. Trigger conditions not yet met. Metric lab integration is the most likely near-term trigger.

At that point, a new ADR should supersede this one.

---

## Non-Decisions (Explicitly Out of Scope for Now)

This ADR does **not** define:
- Versioning schemes
- Release processes
- Migration tooling
- Deprecation mechanics
- API stability guarantees

Those topics are intentionally postponed.

---

## Consequences

### Positive
- Avoids premature or brittle guarantees
- Preserves flexibility during early evolution
- Makes the absence of rules explicit rather than accidental

### Negative
- Contributors must exercise judgment when making breaking changes
- Some uncertainty remains about long-term guarantees

These consequences are accepted intentionally.

---

## Notes

This ADR is a placeholder by design.

Its purpose is to ensure that when rules for evolution and stability are introduced, they are:
- explicit
- deliberate
- consistent with ADR-001 through ADR-003

Until then, change is governed by those ADRs and by careful review.
