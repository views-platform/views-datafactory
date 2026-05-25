
# ADR-012: Four-Layer Data Architecture

**Status:** Accepted
**Date:** 2026-03-20
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Supersedes:** ADR-002 (Topology and Dependency Rules)

---

## Context

ADR-002 defined a 3-layer topology: foundation (Layer 0), independent sources + grid (Layer 1), compilation (Layer 2). This served the system well through its first six definitions of done.

Investigation of real UCDP data revealed that compilation conflates two fundamentally different concerns:

1. **Consolidation** — combining multiple raw snapshots (annual releases, candidate versions) into a single, lossless event store. This is stable work: once the consolidation logic is correct, it changes only when new data sources are added.

2. **Viewpoint building** — applying opinionated rules (survivorship, temporal distribution, uncertainty handling) to produce a single materialized view for downstream consumption. This is volatile work: the rules change as research progresses.

These concerns have different change rates, different owners, and different failure modes. Merging them into a single "compilation" layer violates the single responsibility principle and forces volatile research decisions to live alongside stable data infrastructure.

A 4-layer architecture separates what changes rarely from what changes often.

---

## Decision

This repository enforces a strict, directional dependency structure across four layers.

> Dependencies must follow declared architectural direction.
> No component may depend on a layer above it.
> Layers are decoupled by the filesystem: data flows as files, not imports.
> Opinions about data are introduced at the latest possible layer.

This is a **graph**, not a pipeline. Not all data flows through all layers. Synthetic data, for example, produces npy directly and reaches consumers without traversing consolidation, viewpoint, or compilation. The layers are independent nodes in a DAG with multiple valid paths.

---

## The Dependency DAG

```
Layer 0 (Foundation):     datafactory_provenance    datafactory_http
                               ^                        ^
                               |                        |
Layer 1 (Sources):        datafactory_priogrid    datafactory_harvester
                               |                        |
                               |        ┌───────────────┘
                               |        |  (filesystem: raw snapshots)
                               |        v
Layer 2 (Consolidation):  datafactory_consolidation
                               |
                               |  (filesystem: consolidated event store)
                               v
Layer 3 (Viewpoint):      datafactory_viewpoint
                               |
                               |  (filesystem: materialized viewpoint)
                               v
Layer 4 (Compilation):    datafactory_compilation ──imports──> datafactory_priogrid
                               |
                               v
                           Consumer nodes
```

Not all data traverses all layers — this is the graph nature of the architecture. GHS-POP and GHS-BUILT-S skip consolidation (single release, nothing to merge; ADR-029, ADR-034).

`datafactory_adapters` sits alongside the graph, not inside it. It converts compiled grid output into consumer formats (DataFrame, FeatureFrame) and imports nothing from `datafactory_*`. It is designed for eventual extraction to `views-pipeline-core`.

### Import Rules

| Package | May import from | Reads filesystem output of |
|---------|----------------|---------------------------|
| `datafactory_provenance` | nothing | nothing |
| `datafactory_http` | nothing | nothing |
| `datafactory_priogrid` | provenance, http | nothing |
| `datafactory_harvester` | provenance, http | nothing |
| `datafactory_consolidation` | provenance | harvester |
| `datafactory_viewpoint` | provenance | consolidation |
| `datafactory_compilation` | provenance, priogrid | viewpoint |
| `datafactory_adapters` | nothing | compilation (reads grid npy) |
| `datafactory_query` | priogrid, adapters | assembly (reads assembled files) |

### Data Flow (Filesystem-Mediated)

- **Layer 1 → Layer 2:** The harvester writes raw Parquet snapshots to `data/`. The consolidator reads these files and writes a consolidated event store.
- **Layer 2 → Layer 3:** The viewpoint builder reads the consolidated store and writes a materialized view (one row per event or event-month).
- **Layer 3 → Layer 4:** The compiler reads the viewpoint output and places events onto the grid, producing npy output with sidecar coordinate arrays.
- **Consumer nodes** (external repos) read Layer 4 output from `data/compiled/`.

The filesystem is the decoupling boundary between every layer. Adding a new source never requires changing the consolidator. Changing viewpoint rules never requires changing the consolidator or the compiler.

### Change Rate Expectations

| Layer | Changes when... | Expected frequency |
|-------|----------------|-------------------|
| Layer 0 (Foundation) | Digest algorithm, ledger schema, source registry, or platform constants change | Rarely (years) |
| Layer 1 (Sources) | Upstream API schema changes or new source added | Occasionally (months) |
| Layer 2 (Consolidation) | New source type requires new consolidation logic | Occasionally (months) |
| Layer 3 (Viewpoint) | Research produces new survivorship rules, uncertainty models, temporal distribution methods | Frequently (weeks/sprints) |
| Layer 4 (Compilation) | New output format or aggregation strategy added | Occasionally (months) |

Layer 3 changes 10x more often than Layer 2. They must be separate.

---

## Package Structure

Each new layer follows the established registry pattern from `datafactory_harvester/sources/`:

```
datafactory_consolidation/           # Layer 2
    consolidators/                   # Source-specific: one per data source
        ucdp.py                      # UCDP annual + candidate → event store
    event_store.py                   # Source-agnostic: append-only Parquet, bitemporal queries

datafactory_viewpoint/               # Layer 3
    builders/                        # Source-specific: one per source × version
        ucdp_v1.py                   # UCDP viewpoint v1: annual wins, even spread, date_end
    survivorship.py                  # Strategy registry (OCP: add strategy = add function)
    temporal_distribution.py         # Strategy registry (OCP: add strategy = add function)
```

Adding a new source means adding `consolidators/<source>.py` and `builders/<source>_v1.py`. No existing files are modified. This is the Open-Closed Principle applied to the DAG. ACLED is now fully integrated with its own consolidator (`consolidators/acled.py`), viewpoint builder (`builders/acled_v1.py`), compiler (ACLED-specific `CompilationConfig`), and assembly integration (see ADR-028).

---

## Forbidden Patterns

All prohibitions from ADR-002 remain in force, plus:

- `datafactory_consolidation` importing from `datafactory_viewpoint` or `datafactory_compilation` (consolidation does not know how its data will be used)
- `datafactory_viewpoint` importing from `datafactory_compilation` (viewpoint does not know about output formats)
- `datafactory_viewpoint` importing from `datafactory_harvester` (viewpoint reads consolidated data, not raw snapshots)
- `datafactory_compilation` importing from `datafactory_consolidation` or `datafactory_harvester` (compiler reads viewpoint output, not raw or consolidated data)
- Any layer importing from a layer above it
- Any layer embedding opinions that belong to a higher layer (e.g., consolidation choosing between event versions)

---

## Enforcement

Independence is enforced by the filesystem: each `datafactory_*` package is a separate top-level package in `src/`. Import violations are caught by `tests/test_import_enforcement.py`, which must be extended to cover the new packages.

---

## Consequences

### Positive

- Volatile research decisions (viewpoint rules) are isolated from stable data infrastructure (consolidation)
- The consolidated event store is reusable: multiple viewpoint versions can coexist
- Adding a new data source requires only Layer 1 + Layer 2 changes
- Changing viewpoint rules requires only Layer 3 changes
- Each layer can be tested, versioned, and audited independently
- The graph nature allows data sources to skip layers (e.g., GHS-POP and GHS-BUILT-S skip consolidation)

> **Note (v1.2.21):** The synthetic module was removed (dead code, zero exports). Synthetic data generation is deferred to a future design.

### Negative

- Two additional packages to maintain
- More filesystem I/O than a monolithic approach
- Contributors must understand which layer owns which decision

These costs are accepted. The separation pays for itself the first time viewpoint rules change without requiring consolidation rework.

---

## Notes

This ADR supersedes ADR-002 and inherits its core principles: directed dependencies, filesystem-mediated data flow, zero peer-to-peer imports between sources. The key evolution is recognizing that "compilation" was hiding two concerns with fundamentally different change rates.

This ADR defines *structural topology only*. It does not define:
- what consolidation must guarantee (ADR-013),
- what viewpoints must provide (ADR-014),
- source-specific rules (ADR-015+),
- boundary contracts (ADR-009),
- or failure handling (ADR-008).

---

## References

- Kleppmann & Riccomini, *Designing Data-Intensive Applications*, 2nd ed., O'Reilly 2026:
  - Ch.1 pp.7-11: Data warehousing, ETL/ELT pipelines, systems of record vs derived data
  - Ch.1 pp.10-11: Systems of record (authoritative, canonical) vs derived data systems (redundant, rebuildable)
  - Ch.1 p.10: The "sushi principle" — raw data is better (motivates lossless consolidation)
  - Ch.10 pp.394-396: Unix philosophy — each program does one thing well; compose via uniform interfaces
  - Ch.12 pp.491-495: System of record vs derived data; derived data is redundant but rebuildable
  - Ch.12 pp.499-501: "Unbundling the database" — compose specialized tools instead of monolithic systems
