
# ADR-006: Intent Contracts for Non-Trivial Classes

**Status:** Accepted
**Date:** 2026-03-17
**Deciders:** Simon Polichinel von der Maase, Claude Code

---

## Context

As views-datafactory is built out from its initial scaffold, classes will be migrated from the metric lab and new classes will be created. During this process, classes tend to accumulate:
- implicit responsibilities,
- undocumented assumptions,
- and behavior that is clear only to their original author.

This is especially dangerous in a data factory where:
- GridConfig defines the coordinate system that all consumers align to -- semantic drift here silently corrupts every downstream analysis,
- HarvesterConfig governs interaction with external APIs whose schema may change without notice,
- ValidationResult determines whether data is accepted into the system -- a misunderstood contract here means corrupt data passes silently,
- provenance logic is mission-critical and must be exactly correct.

Tests alone are insufficient to preserve *intent*:
they verify current behavior, not what the class is **meant** to do.

To prevent semantic drift, non-trivial classes require an explicit, human-readable declaration of intent.

---

## Decision

All **non-trivial and substantial classes** in this repository must have an explicit **intent contract**.

An intent contract is a short, human-readable description of:
- what the class is intended to do,
- what it is explicitly *not* responsible for,
- and the guarantees it provides to its callers.

The intent contract does **not** need to be a full technical specification,
but it must be:
- unambiguous,
- readable by humans,
- and consistent with tests and implementation.

---

## What Qualifies as a Non-Trivial Class

A class is considered **non-trivial** if it meets one or more of the following:

- Defines the coordinate system that all consumers align to (GridConfig, TemporalConfig, SpatioTemporalGrid)
- Governs data acquisition from external APIs (HarvesterConfig, source-specific clients)
- Determines whether data passes or fails validation (ValidationResult, schema contracts)
- Writes provenance records (ledger functions, digest computation)
- Produces compiled output that downstream models consume (compilation functions, npy writers)
- Orchestrates multiple components (fetch-validate-store-provenance pipeline)
- Maintains internal state across operations
- Could cause silent data corruption if misunderstood

Whether a class is non-trivial is a **review decision**.

When in doubt, treat the class as non-trivial.

---

## Priority Candidates

The following classes should receive intent contracts as they are implemented:

1. **GridConfig** -- defines spatial coordinate system (from `lab_grid/config.py`)
2. **TemporalConfig** -- defines temporal coordinate system (from `lab_grid/temporal_config.py`)
3. **SpatioTemporalGrid** -- composes spatial + temporal backbones (from `lab_grid/spatiotemporal.py`)
4. **HarvesterConfig** -- governs API interaction parameters
5. **ValidationResult** -- determines data acceptance/rejection
6. **CompilationConfig** -- governs compilation behavior (new, no metric lab source)
7. **SourceEntry** (`datafactory_provenance.source_registry`) -- source registry backbone
8. **AssemblyConfig** (`scripts/assemble_grid.py`) -- grid assembly configuration
9. **ViewpointConfig** (`datafactory_viewpoint.viewpoint_config`) -- viewpoint builder configuration

---

## Form of an Intent Contract

An intent contract must include, at minimum:

- **Purpose:** what the class is for
- **Non-goals:** what the class explicitly does *not* do
- **Inputs and assumptions:** what it expects to be true
- **Outputs and guarantees:** what it promises in return
- **Failure behavior:** how it fails when assumptions are violated

The contract may live as:
- a dedicated file in `docs/CICs/` (for especially central classes),
- a standalone design note,
- or a clearly marked docstring or markdown file referenced from the code.

The format is flexible; clarity is not.

---

## Relationship to Tests

Intent contracts and tests must agree.

- Tests should reflect the declared intent
- Changes to intent require updating the contract
- Changes that violate the declared intent are bugs, not refactors

If behavior changes but intent does not, tests must be updated.
If intent changes, it must be made explicit.

---

## Enforcement

- Introducing a non-trivial class without an intent contract is grounds for blocking a change
- Modifying a non-trivial class in ways that contradict its intent contract is not permitted
- Reviewers are expected to reference intent contracts when evaluating changes

This rule is enforced socially and through review.

---

## Consequences

### Positive
- Preserves architectural intent during migration from the metric lab
- Makes refactoring safer and more principled
- Reduces cognitive load for reviewers and new contributors
- Prevents classes from silently changing meaning

### Negative
- Requires additional upfront thought and writing
- Some changes may require updating documentation alongside code

These costs are accepted intentionally.

---

## Notes

Intent contracts are not bureaucracy.

They are a mechanism for ensuring that **the system continues to mean what we think it means**, even as code is migrated, refactored, and extended.
