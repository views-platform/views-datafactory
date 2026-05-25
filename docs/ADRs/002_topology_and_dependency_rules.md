
# ADR-002: Topology and Dependency Rules

**Status:** Superseded by ADR-012
**Date:** 2026-03-17
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Superseded:** 2026-03-20 — See [ADR-012: Four-Layer Data Architecture](012_four_layer_data_architecture.md)

---

## Context

views-datafactory is structured as a graph of 5 top-level Python packages under `src/`, each with a `datafactory_` prefix. Unlike a traditional layered system, the topology is a **directed acyclic graph (DAG)** of independent nodes connected by filesystem-mediated data flow.

Without explicit topology rules:
- source nodes begin depending on compilation or consumer code,
- circular dependencies emerge between packages,
- the graph collapses into a pipeline where order matters,
- and system evolution becomes constrained by accidental coupling.

A clear rule is required to define **who may depend on whom** -- both in code imports and in data flow.

---

## Decision

This repository enforces a strict, directional dependency structure.

> Dependencies must follow declared architectural direction.
> No component may depend on a layer above it.
> Source nodes must not depend on each other.

Dependency direction is part of the system's structural integrity.

Violations are architectural defects.

---

## The Dependency DAG

```
Layer 0 (Foundation):    datafactory_provenance
                              ^
                              |
Layer 1 (Independent):   datafactory_priogrid    datafactory_harvester
                              ^
                              |
Layer 2 (Compilation):   datafactory_compilation
```

### Import Rules

- `datafactory_provenance` imports nothing from any other `datafactory_*` package (Layer 0).
- `datafactory_priogrid` and `datafactory_harvester` each import **only** from `datafactory_provenance` (Layer 1). They are independent peers with **zero peer-to-peer imports**.
- `datafactory_compilation` imports from `datafactory_provenance` and `datafactory_priogrid` (for coordinate arrays and grid config). It reads harvester output as **files on disk** -- never as code imports (Layer 2).
- No package imports from `datafactory_compilation`. Consumers read its filesystem output.

### Data Flow (Filesystem-Mediated)

Runtime data flow is a graph, not a layer stack:

- Source nodes (harvester) write to `data/` independently.
- Compilation edges read from `data/` and write compiled output to `data/compiled/`.
- Consumer nodes (external repos) read from `data/compiled/`.

The filesystem is the decoupling boundary between sources and compilation. This ensures that adding a new source never requires changing the compiler, and adding a new output format never requires changing a source.

---

## Architectural Boundaries

Each component must:

- Declare its responsibility zone (see ADR-001),
- Respect dependency direction (this ADR),
- Avoid implicit cross-layer coupling.

This ADR governs **structural dependency direction only**.

> The definition and validation of boundary contracts (schemas, configuration validation, handshake rules) are governed separately by ADR-009.

Topology defines *who may depend on whom*.
ADR-009 defines *what must be true at the boundary*.

---

## Forbidden Patterns

The following dependency violations are explicitly prohibited:

- `datafactory_harvester` importing from `datafactory_priogrid` (sources don't know about the grid)
- `datafactory_compilation` importing from `datafactory_harvester` (compilation reads files, not source-specific code)
- `datafactory_priogrid` importing from `datafactory_compilation` or `datafactory_harvester` (the coordinate system is independent of data)
- Any package importing from `datafactory_compilation` (consumers read filesystem output, not compiler code)
- Any `datafactory_*` package importing from consumer repositories (e.g., the metric lab)
- Cross-layer utility shortcuts that bypass the declared DAG

If a dependency feels "convenient but wrong," it probably is.

---

## Enforcement

Independence is enforced by the filesystem: each `datafactory_*` is a separate top-level package in `src/`. This makes violations visible as explicit import statements that can be caught by code review, linting rules, or import analysis.

---

## Consequences

### Positive

- Adding a new source never changes existing sources or the compiler
- Adding a new output format never changes existing harvesters
- Each package can be tested in isolation
- The graph architecture scales to multiple sources and multiple consumers

### Negative

- Some data must flow through the filesystem even when an in-memory shortcut would be faster
- The compiler cannot use source-specific knowledge without it being declared in configuration
- Requires discipline when migrating code from the metric lab (where some boundaries were less strict)

These costs are accepted intentionally.

---

## Notes

This ADR defines structural direction of dependencies.

It does not define:

- boundary contract validation (ADR-009),
- semantic authority (ADR-003),
- or testing obligations (ADR-005).

Topology governs structure.
Contracts govern interaction.
