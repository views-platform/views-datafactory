
# ADR-009: Boundary Contracts and Configuration Validation

**Status:** Accepted
**Date:** 2026-03-17
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Amended:** 2026-11-02 — the views-frames range named in Context item 7 is now `>=1.10.2,<4`. The boundary decision is unchanged; see the Amendment at the end of Consequences. *(Header pointer per ADR-030's precedent: the stale range sits in Context, and a reader who stops there would leave with a constraint that is no longer declared.)*

---

## Context

Complex systems fail most often at boundaries:

- between modules,
- between configuration and runtime,
- between data producers and consumers,
- between raw source data and compiled grid output.

views-datafactory has nine packages across four layers (ADR-012), with data flowing through the filesystem between them. The nine packages are: provenance, http, priogrid, harvester, consolidation, viewpoint, compilation, adapters, and query. The most critical boundaries are:

1. **Configuration to runtime** -- frozen dataclasses with `__post_init__` validation must catch invalid parameters before any operation begins.
2. **Harvester to filesystem** -- raw Parquet snapshots with content digests must be validated before storage.
3. **Filesystem to consolidator** -- the consolidator reads source snapshots and must verify their integrity (digest match, expected schema) before appending to the event store.
4. **Consolidator to viewpoint builder** -- the viewpoint builder reads the consolidated store and must verify its integrity and completeness before applying survivorship rules.
5. **Viewpoint to compiler** -- the compiler reads the viewpoint output and must verify schema conformance before grid placement.
6. **Compiler to consumer** -- compiled npy output with sidecar coordinate arrays must conform to the declared shape contract.
7. **Assembly to adapters** -- adapters consume assembled grid files (`grid.npy`, `pgids.npy`, `time_steps.npy`, `feature_names.json`) and produce FeatureFrame (views-frames `>=1.0,<2`) or DataFrame. FeatureFrame output has shape `(N, D, 1)` with `SpatioTemporalIndex` validated for time/unit/level. External dependency boundary: views-frames.

Ambiguous configuration, hidden defaults, and implicit contracts introduce silent semantic drift and runtime fragility. To preserve architectural integrity and fail-loud guarantees (ADR-003), all external and internal boundaries must be explicit and validated.

---

## Decision

This repository adopts the following invariants:

> All architectural boundaries must declare explicit contracts.
> All configuration must be validated at entry.
> No semantic defaults may exist silently.

---

## 1. Boundary Contracts

Every boundary between components must define:

- Explicit input schema
- Explicit output schema
- Declared invariants
- Failure semantics

### Domain-Specific Boundaries

**GridConfig boundary:** `__post_init__` validates resolution > 0, west < east, south < north, resolution evenly divides extent. Violations raise immediately. (Implemented in `datafactory_priogrid/grid_config.py`.)

**UcdpAnnualConfig boundary (implemented):** `__post_init__` validates end_year >= start_year, page_size >= 1, max_retries >= 1, version non-empty. (Implemented in `datafactory_harvester/sources/ucdp_annual.py`.)

**Harvester-to-filesystem boundary (implemented):** ValidationResult checked before `save_event_snapshot`. Content digest computed via `datafactory_provenance.compute_content_digest`. Schema snapshot captured. Comparison against previous snapshot detects added/removed/revised events.

**CompilationConfig boundary (implemented):** `__post_init__` validates features non-empty. Source existence checked at compile time (FileNotFoundError). Feature list declared in config, never inferred from Parquet columns.

**Compiled output contract (implemented):** Shape is always `(n_steps, nrow, ncol, n_features)` — dimension order `[T, H, W, C]` (time, height, width, channels). Coordinate arrays (`pgids.npy`, `time_steps.npy`, `feature_names.json`) shipped alongside `grid.npy`. Provenance JSON links source digest to output digest. See ADR-024 for the full 4D grid invariant specification.

**SourceEntry boundary (implemented):** `SourceEntry` frozen dataclass in `datafactory_provenance.source_registry` validates name non-empty, env vars non-empty, features non-empty, and `slo_hours` positive.

**AssemblyConfig boundary (implemented):** `AssemblyConfig` frozen dataclass in `scripts/assemble_grid.py` validates `output_dtype` against a whitelist, `disk_space_margin` >= 1.0, `admin_numeric_fields` non-empty and no duplicates.

Implicit contracts are prohibited. If a boundary assumption cannot be declared clearly, the boundary is ill-defined and must be redesigned.

---

## 2. Configuration as First-Class Artifact

Configuration is not a convenience layer. It is an architectural artifact.

Configuration must:

- Be explicit (frozen dataclasses with all fields declared)
- Be versionable (deterministic serialization for provenance)
- Be externally inspectable (readable without running code)
- Be validated before execution (`__post_init__` checks)
- Not rely on hidden defaults

Changing configuration must not silently alter system meaning.

---

## 3. Validation at Entry (Handshake Principle)

All configuration and external inputs must be validated at the system boundary.

Validation must occur:

- Before state mutation
- Before execution begins
- Before provenance is recorded

The system must fail early if:

- Required fields are missing
- Types are incorrect
- Redundant parameters disagree
- Declared invariants are violated
- Content digests do not match expected values

Borrowed or assumed state is prohibited.

---

## 4. Separation of Configuration Domains

Configuration domains must be separated conceptually:

- **Operational parameters** (affect computation): grid resolution, aggregation strategy, temporal range, covariance parameters
- **Transport parameters** (affect data acquisition): API base URLs, page sizes, retry counts, timeouts
- **Provenance parameters** (affect audit trail): output paths, ledger paths, digest algorithms

Cross-domain coupling must be explicit. Configuration that affects behavior must not be disguised as metadata.

---

## 5. Redundancy and Consistency Checks

Where ambiguity risk is high, explicit redundancy is preferred:

- Declaring both grid dimensions and cell count (consistency check: 360 x 720 = 259,200)
- Declaring both temporal range and expected step count (consistency check: months between start and end)
- Shipping coordinate arrays alongside data arrays (consistency check: shapes must match)
- Recording both input digests and output digest in provenance (enables rebuild verification)

Redundant declarations must be validated for consistency.
Silent derivation is discouraged where semantic meaning is involved.

---

## 6. Failure Semantics

Configuration validation failures must:

- Be logged (ADR-008)
- Be raised explicitly (ADR-008)
- Halt execution

Warnings are insufficient for structural configuration errors.

---

## Consequences

### Positive

- Eliminates hidden configuration drift
- Reduces boundary fragility
- Strengthens fail-loud guarantees
- Improves reproducibility and traceability
- Makes the provenance chain verifiable end-to-end

### Negative

- Requires explicit schemas
- Adds validation boilerplate
- Increases up-front configuration clarity requirements

These costs are accepted.

---

### Amendment 2026-11-02 — the views-frames range in Context item 7 (#527)

Context item 7 reads *"FeatureFrame (views-frames `>=1.0,<2`)"*. The declared range is now
**`>=1.10.2,<4`** (`pyproject.toml`). The original text is left as written, per the repository's
dated-amendment rule; this section carries the current fact.

It was wrong in two separate ways, and they are worth separating because only one of them is
tonight's change.

**The floor had been stale since 2026-08-02.** C-337 raised it from `>=1.0` to `>=1.10.2` because
views-frames changed how MAP and HDI are computed three times in MINOR releases, and a floor
constrains the resolver rather than our import list. This ADR was not updated then. The lesson is
the ADR's own: a boundary stated in prose is an implicit contract unless something reads it.

**The cap moved on 2026-11-02 (#527).** `<2` was the last constraint on the platform holding
views-frames below 3.0.0, whose reconciliation fix (views-frames ADR-030) stops a draw with an
all-zero grid silently losing a country's fatality mass. A fresh resolve of views-models' forecast
lane fell back to views-pipeline-core 3.3.5 and views-frames 1.11.0 — exit 0, no warning — because
this package declared `<2`.

**The boundary invariant itself is unchanged, and that is a measurement rather than a hope.**
views-frames 2.0.0 (ADR-028) makes a frame's `index` require a real `SpatioTemporalIndex` and makes
`frame.values` read-only. This repository already satisfies both: both frames are constructed on a
real `SpatioTemporalIndex` — `grid_to_feature_frame()` in
`src/datafactory_adapters/grid_to_feature_frame.py` and `build_contract_frame()` in
`scripts/generate_contract_fixture.py` — and nothing in `src/`, `scripts/`, `tests/` or
`examples/` writes into `.values`. Verified against 3.0.0 in a clean venv on 2026-11-02: the full
suite, `mypy --strict` and `ruff` all clean, including ADR-050's fixture drift alarm — so 3.0.0
writes a byte-identical FeatureFrame layout, and the shape contract `(N, D, 1)` with time/unit/level
validation holds exactly as stated above.

The floor stays at 1.10.2 deliberately. The `>=3.0.0` floor belongs where reconciliation happens —
views-pipeline-core 3.4.0 carries it — and views-baseline 1.0.3 shipped this same shape. This
package does not reconcile.

---

## Notes

This ADR does not prescribe:

- Specific file layouts
- Specific configuration libraries
- Specific schema frameworks

Operational configuration structures may vary by module,
provided they comply with the invariants defined here.

## References

- Kleppmann & Riccomini, *Designing Data-Intensive Applications*, 2nd ed., O'Reilly 2026:
  - Ch.4 p.112: Backward and forward compatibility — essential for systems where data outlives code
  - Ch.4 pp.129-130: Data outlives code — "the desirable behavior is usually for the old code to keep the new field intact, even though it couldn't interpret it"
  - Ch.4 p.127: Schemas as documentation — "the schema is a valuable form of documentation"; schemas enable compile-time type checking and compatibility verification before deployment
