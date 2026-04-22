
# ADR README and Governance Map

This repository uses Architectural Decision Records (ADRs) to govern
structural, semantic, and operational behavior.

ADRs are divided into two categories:

1. **Constitutional ADRs (000-009)**
   Foundational architectural rules that apply across the system.

2. **Project-Specific ADRs (010+)**
   Domain, implementation, or feature-level decisions.

---

## Constitutional ADRs

These ADRs define system philosophy and governance:

- **ADR-000** -- Use of Architecture Decision Records
  Establishes the ADR practice.

- **ADR-001** -- Ontology of views-datafactory
  Defines what concepts exist: Source Nodes, The Grid, Compilation Edges, Configurations, Provenance Records.

- **ADR-002** -- Topology and Dependency Rules
  Defines the DAG: core (L0) -> grid/harvester/synthetic (L1) -> compiler (L2). Filesystem-mediated data flow.

- **ADR-003** -- Authority of Declarations Over Inference
  Defines where semantic authority lives. Fail-loud on ambiguity.

- **ADR-004** -- Rules for Evolution and Stability (Deferred)
  Placeholder for future stability guarantees. Revisit when consumers formally depend on this repo.

- **ADR-005** -- Testing as Mandatory Critical Infrastructure
  Defines red / beige / green test doctrine for data integrity.

- **ADR-006** -- Intent Contracts for Non-Trivial Classes
  Requires declared class-level purpose. Priority: GridConfig, HarvesterConfig, ValidationResult.

- **ADR-007** -- Silicon-Based Agents as Untrusted Contributors
  Governs automated modification. Heightened scrutiny on provenance and grid coordinate logic.

- **ADR-008** -- Observability and Explicit Failure
  Defines fail-loud + log requirements. JSONL provenance as primary observability.

- **ADR-009** -- Boundary Contracts and Configuration Validation
  Defines explicit interface contracts: frozen dataclasses, digest verification, shape contracts.

These ADRs form the architectural constitution of the repository.

---

## Project-Specific ADRs

- **ADR-010** -- GridConfig Contains Only Spatial Parameters
  Paths and URLs removed from GridConfig (SRP). Injected at call sites.

- **ADR-011** -- Fail Loud, No Stale Data Serving
  System crashes on failure. No automatic fallback.

- **ADR-012** -- Four-Layer Data Architecture
  Graph topology: provenance (L0) → priogrid/harvester/synthetic (L1) → consolidation (L2) → viewpoint (L3) → compilation (L4). Supersedes ADR-002.

- **ADR-013** -- Consolidation Principles
  Lossless, append-only, bitemporal. No fields dropped.

- **ADR-014** -- Viewpoints as Derived Views
  Opinionated, versioned, rebuildable. Multiple viewpoints coexist.

- **ADR-015** -- UCDP Consolidation and Viewpoint Specifics
  Three-source consolidation (annual + candidate + .9). Survivorship and distribution strategies.

- **ADR-016** -- Viewpoint Profiles
  Named presets (e.g., production_parity) for strategy + filter combinations.

- **ADR-017** -- Vintage-Aware Consolidation
  Content-addressed dedup. Mutable versions preserved as distinct vintages.

- **ADR-018** -- Operational Resilience Policy
  Pipeline stays fail-loud. Operators may serve bounded-stale data under documented conditions.

- **ADR-019** -- Visualization Style Guide
  Shared style module (`scripts/viz_style.py`) for all visualization scripts. Tufte-derived aesthetic.

- **ADR-020** -- Technical Risk Register
  Formalized risk register as governance artifact. Active + resolved archive split.

- **ADR-021** -- Zarr as Servable Export Format
  xarray-compatible zarr store for HTTP serving. One variable per feature, 12-month chunks.

- **ADR-022** -- Tag-Based Deployment Gate
  Server runs a specific tagged release, not a branch tip. Operator controls version via `~/.views-deploy-tag`. Fail-loud on misconfiguration.

- **ADR-023** -- Viewpoint Builder Invariants
  Defines invariants for viewpoint construction: survivorship, distribution, and filtering rules.

- **ADR-024** -- Compilation Grid Invariants
  Defines invariants for grid compilation: spatial join, temporal alignment, feature ordering.

- **ADR-025** -- Country Identity Uses GAUL Codes
  GAUL-2014 as the authoritative country coding system. No G&W or C-Shapes.

- **ADR-026** -- Credential Management Strategy
  Env vars + netrc for credential resolution. Credentials are not configuration. Fail-loud on missing. No `.env` files, no `python-dotenv`.

These must comply with the constitutional ADRs above.

---

## Governance Structure (Conceptual Map)

- **Ontology (001)** defines what exists.
- **Topology (002)** defines structural direction.
- **Authority (003)** defines who owns meaning.
- **Boundary Contracts (009)** define interaction rules.
- **Observability (008)** enforces failure semantics.
- **Testing (005)** verifies system integrity.
- **Intent Contracts (006)** bind class-level behavior.
- **Automation Governance (007)** constrains silicon-based agents.

Together, these define the invariant layer of the system.

---

## Recommended Adoption Order

Constitutional ADRs are designed to be adopted incrementally:

### Phase 1 -- Foundation
- **ADR-000** (Use of ADRs) -- establishes the practice
- **ADR-003** (Authority of Declarations) -- the fail-loud invariant
- **ADR-008** (Observability and Explicit Failure) -- failure handling

These three are load-bearing. Start here.

### Phase 2 -- Structure
- **ADR-001** (Ontology) -- define what exists
- **ADR-002** (Topology) -- define dependency direction

### Phase 3 -- Testing & Intent
- **ADR-005** (Testing Doctrine) -- red/beige/green framework
- **ADR-006** (Intent Contracts) -- class-level purpose declarations

### Phase 4 -- Boundaries & Automation
- **ADR-007** (Silicon-Based Agents) -- AI governance
- **ADR-009** (Boundary Contracts) -- configuration validation

ADR-004 (Evolution & Stability) is intentionally deferred and should be
revisited when external consumers or reproducibility requirements emerge.
