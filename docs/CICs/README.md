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
- `UcdpConsolidationConfig.md` -- immutable UCDP consolidation configuration (source dirs, ledger paths)
- `ViewpointConfig.md` -- immutable viewpoint configuration (strategies, filters, version)
- `ValidationResult.md` -- structured validation outcome (valid, errors, digest)
- `ComparisonResult.md` -- structured revision detection outcome (added, removed, revised)
- `ConsolidationResult.md` -- immutable consolidation result (counts, digest)
- `ViewpointResult.md` -- immutable viewpoint build result (counts, digest, version)
- `PriogridStaticConfig.md` -- immutable PRIO-GRID static feature harvest configuration
- `ShapefileHarvesterConfig.md` -- immutable PRIO-GRID shapefile download configuration
- `GaulAdminConfig.md` -- immutable GAUL 2024 admin boundary harvest configuration
- `AcledConfig.md` -- immutable ACLED harvest configuration (year range, event types, OAuth2 transport)
- `AcledConsolidationConfig.md` -- immutable ACLED consolidation configuration (source dir, ledger paths)
- `AcledViewpointConfig.md` -- immutable ACLED viewpoint configuration (event type filter, version)
- `RemoteConfig.md` -- immutable remote server configuration (address, URL paths, scheme)
- `GhsPopConfig.md` -- immutable GHS-POP harvest configuration (epochs, resolution, download URLs)
- `GhsPopViewpointConfig.md` -- immutable GHS-POP viewpoint configuration (spatial aggregation, temporal interpolation)
- `GhsBuiltSConfig.md` -- immutable GHS-BUILT-S harvest configuration (epochs, resolution, download URLs)
- `GhsBuiltSViewpointConfig.md` -- immutable GHS-BUILT-S viewpoint configuration (spatial aggregation, temporal interpolation)
- `VdemConfig.md` -- immutable V-Dem harvest configuration (download URL, variables, version)
- `VdemViewpointConfig.md` -- immutable V-Dem viewpoint configuration (crosswalk, temporal range, variables)
- `ShdiViewpointConfig.md` -- immutable SHDI viewpoint configuration (GDL crosswalk, temporal range, intensive indices)
- `AssemblyConfig.md` -- immutable assembly configuration (compiled grid paths, output directory)
- `PrecomputedData.md` -- precomputed state container for V-Dem grid verification (24 fields, per-feature temporal handling)
- `PregriddedCompilationConfig.md` -- immutable pre-gridded compilation configuration (GHS-POP, GHS-BUILT-S)
- `SourceEntry.md` -- immutable source registry entry (name, features, provenance paths)
- `grid_to_country_month.md` -- grid-to-country-month aggregation function contract
- `load_dataset.md` -- **the public consumer entry point** (ADR-050): region/time/feature subsetting, the three declared output formats, the `storage_options` seam, and which failures are loud

---

## Governance Relationship

Intent Contracts are governed by:

- ADR-006 (Intent Contracts for Non-Trivial Classes)
- ADR-003 (Authority of Declarations)
- ADR-005 (Testing Doctrine)

If a class changes meaning, its Intent Contract must be updated.
