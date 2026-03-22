# Class Intent Contracts README

This directory contains **Intent Contracts** as defined in ADR-006.

An Intent Contract is a human-readable, unambiguous declaration of:

- what a non-trivial class is meant to do,
- what it must never do,
- its invariants,
- and its failure semantics.

Intent Contracts are architectural artifacts.
They are not implementation documentation.

---

## When Is an Intent Contract Required?

An Intent Contract is mandatory for:

- Core domain classes (GridConfig, TemporalConfig, SpatioTemporalGrid)
- Architectural boundary classes (HarvesterConfig, CompilationConfig)
- Validation components (ValidationResult, schema contracts)
- State-owning components (provenance ledger writers)
- Classes that enforce invariants
- Classes that modify semantics or transformation

Trivial value objects and pure utility functions do not require one.

---

## Structure of an Intent Contract

Each contract must define:

1. Purpose
2. Responsibility Boundary
3. Invariants
4. Explicit Non-Responsibilities
5. Failure Semantics
6. Observable Effects (if applicable)

Contracts must be clear enough that:

- Tests (ADR-005) can be derived from them.
- Architectural violations can be detected.
- Silicon-based agents cannot reinterpret intent (ADR-007).

---

## Active Contracts

- `GridConfig.md` -- immutable spatial grid configuration (resolution, bounds, CRS)
- `TemporalConfig.md` -- immutable temporal backbone configuration (year/month range)
- `SpatioTemporalGrid.md` -- composed spatiotemporal index with lazy coordinate generation
- `CompilationConfig.md` -- immutable compilation configuration (features, paths, grid/temporal)
- `UcdpAnnualConfig.md` -- immutable UCDP annual harvest configuration
- `UcdpCandidateConfig.md` -- immutable UCDP candidate monthly harvest configuration
- `UcdpDot9Config.md` -- immutable UCDP .9 consolidated monthly harvest configuration
- `ViewpointConfig.md` -- immutable viewpoint configuration (strategies, filters, version)
- `ValidationResult.md` -- structured validation outcome (valid, errors, digest)
- `ComparisonResult.md` -- structured revision detection outcome (added, removed, revised)
- `ConsolidationResult.md` -- immutable consolidation result (counts, digest)
- `ViewpointResult.md` -- immutable viewpoint build result (counts, digest, version)
- `PriogridStaticConfig.md` -- immutable PRIO-GRID static feature harvest configuration
- `ShapefileHarvesterConfig.md` -- immutable PRIO-GRID shapefile download configuration

---

## Governance Relationship

Intent Contracts are governed by:

- ADR-006 (Intent Contracts for Non-Trivial Classes)
- ADR-003 (Authority of Declarations)
- ADR-005 (Testing Doctrine)

If a class changes meaning, its Intent Contract must be updated.
