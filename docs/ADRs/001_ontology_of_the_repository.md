
# ADR-001: Ontology of views-datafactory

**Status:** Accepted
**Date:** 2026-03-17
**Deciders:** Simon Polichinel von der Maase, Claude Code

---

## Context

views-datafactory is the data foundation for the VIEWS conflict forecasting platform. Its architecture is a **graph of independent nodes** connected by typed edges:

- **Source nodes** produce raw data independently (harvesters fetch from external APIs).
- **Compilation edges** transform source data into consumer-specific formats (grid npy now, panel parquet and others later).
- **Consumer nodes** (the metric lab, views-hydranet, other VIEWS repos) read compiled outputs.

Without an explicit ontology, systems tend to accumulate:
- implicit concepts,
- overloaded abstractions,
- objects that mix responsibilities (e.g., a class that both fetches data AND compiles it onto the grid),
- semantics that exist only in developers' heads.

This is especially dangerous in a data factory whose compiled outputs inform humanitarian forecasts. An explicit ontology is required to define **what kinds of things are allowed to exist** in this repository, and which kinds of things are explicitly disallowed.

---

## Decision

This repository defines a **closed set of conceptual categories** ("entities") that are allowed to exist.

Each category has:
- a clear semantic role,
- an expected stability level,
- explicit boundaries.

Anything that does not clearly belong to one of these categories is considered **out of scope** and must be re-designed or rejected.

---

## Core Ontological Categories

| Category | Purpose | Authority | Stability | Must Not Contain |
|----------|---------|-----------|-----------|-----------------|
| **Source Nodes** (harvester) | Produce raw data independently from external sources | High -- own the raw data contract | Evolving (new sources expected) | Compilation logic, consumer awareness, grid placement, knowledge of other sources |
| **The Grid** (spatial backbone + temporal backbone) | Define the shared coordinate system (PRIO-GRID 259,200 cells at 0.5 deg, monthly 1989-2024) that all compiled data aligns to | Authoritative -- the single source of truth for spatial/temporal coordinates | Stable (resolution and coordinate scheme are load-bearing) | Data values, source-specific logic, compilation, consumer formatting |
| **Compilation Edges** (compiler) | Transform source data into consumer-specific formats by placing events onto the grid | Medium -- derived from sources + grid | Evolving (new formats, aggregation strategies expected) | Data fetching, source-specific API logic, model evaluation, consumer-specific post-processing |
| **Configurations** (frozen dataclasses) | Explicit, validated, immutable parameter sets that govern every operation | Authoritative -- the declared intent for each operation | Stable pattern, evolving instances | Runtime state, mutable fields, inferred defaults, implicit fallbacks |
| **Provenance Records** (JSONL ledgers, content digests) | Immutable audit trail linking every output to specific inputs + config | Mission-critical -- the system's memory | Append-only, never modified or deleted | Derived analytics, visualization, convenience queries, mutable state |
| **Consolidated Event Store** (consolidation layer) | Lossless, append-only, version-aware union of all source snapshots. Preserves every version of every event with bitemporal metadata. | Authoritative -- the single source of truth for "what do we know and when did we know it" | Stable (changes when new sources added; existing records never modified) | Survivorship decisions, temporal distribution, uncertainty resolution, aggregation, grid placement |
| **Viewpoints** (materialized views) | Opinionated, rebuildable, versioned perspectives over the consolidated store. Each viewpoint applies explicit survivorship rules, temporal distribution, and uncertainty handling. Multiple viewpoints coexist. | Derived -- disposable and rebuildable from the consolidated store + configuration | Volatile (changes as research progresses; expected to have multiple coexisting versions) | Raw data storage, consolidation logic, grid placement, output formatting |

---

## Stability Rules

- **The Grid** is expected to be stable across the lifetime of the project. Changing the coordinate system is a breaking change for all consumers.
- **Configurations** follow a stable pattern (frozen dataclasses with `__post_init__` validation) but individual config types evolve as modules are implemented.
- **Source Nodes** are explicitly allowed to evolve: new sources are added, existing source schemas may change as upstream providers revise their APIs.
- **Compilation Edges** evolve as new output formats and aggregation strategies are added.
- **Provenance Records** are append-only. The ledger format may evolve (new fields), but existing entries are never modified.
- **Consolidated Event Stores** are append-only and stable. New sources trigger new consolidation logic, but existing records are never modified or deleted (ADR-013).
- **Viewpoints** are volatile by design. They are rebuilt when rules change. Multiple versions coexist (ADR-014).

Stability is a design constraint, not a preference.

---

## Explicit Non-Entities

The following are **not allowed** as first-class concepts:

- **Implicit or inferred semantics:** inferring grid resolution from array shape rather than from GridConfig; inferring UCDP version from a file path rather than from HarvesterConfig
- **Hybrid objects:** a class that both fetches data AND compiles it onto the grid; a class that both generates data AND evaluates its fidelity
- **Pipeline assumptions:** any object that assumes source A runs before source B, or that compilation happens immediately after harvesting
- **Consumer-aware sources:** a harvester that formats its output for a specific downstream model; a source that knows about the metric lab's ExperimentFrame
- **Silent fallbacks:** a harvester that returns empty data when the API fails instead of raising; a compiler that fills missing cells with zeros without recording it in provenance
- **"Convenience" abstractions** that hide meaning: wrapper functions that obscure which source or config is being used

If a concept matters, it must be explicit. If it does not fit a category above, it does not belong.

---

## Consequences

### Positive
- Shared vocabulary across contributors
- Reduced conceptual drift
- Clear review criteria for new abstractions
- New sources, formats, and consumers can be added without violating existing categories

### Negative
- Requires upfront discipline
- Some refactors may be blocked until concepts are clarified

These trade-offs are accepted.

---

## Notes

This ADR defines *what exists*, not *how components depend on each other*.
Dependency rules are defined separately in ADR-012 (superseding ADR-002).
