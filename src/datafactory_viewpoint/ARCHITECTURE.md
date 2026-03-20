# datafactory_viewpoint -- Architecture

## Purpose

Opinionated, versioned, rebuildable materialized views over consolidated event stores. Each viewpoint applies explicit survivorship rules, temporal distribution strategies, and uncertainty handling to produce a single perspective on the data. Multiple viewpoints coexist over the same consolidated base. This implements the golden record concept from master data management (ADR-014). This is a Layer 3 package in the dependency DAG (ADR-012).

## Responsibility Boundary

**Owns:**
- Survivorship rules (which version of an event wins when sources disagree)
- Temporal distribution (how summary events spanning multiple months are spread across time)
- Uncertainty handling (whether and how `date_prec`, `where_prec`, `low`/`high` influence output)
- Field selection (which fields from the consolidated store propagate to the viewpoint)
- Month assignment (whether `date_start` or `date_end` determines the event's month)
- Viewpoint configuration versioning

**Does NOT own:**
- Data fetching or harvesting (datafactory_harvester — Layer 1)
- Raw snapshot consolidation (datafactory_consolidation — Layer 2)
- Grid placement or aggregation (datafactory_compilation — Layer 4)
- Output format decisions (datafactory_compilation — Layer 4)

## Dependency Rules

**May import:** `datafactory_provenance`
**Reads filesystem output of:** `datafactory_consolidation` (consolidated event store)
**Must never import:** `datafactory_priogrid`, `datafactory_harvester`, `datafactory_consolidation`, `datafactory_compilation`, `datafactory_synthetic`, or any consumer

## Package Structure

```
datafactory_viewpoint/
    __init__.py                    # Package docstring, empty __all__ until implementation
    ARCHITECTURE.md                # This file
    builders/
        __init__.py                # Registry: register_builder, build_viewpoint, list_builders
        (ucdp_v1.py)              # UCDP viewpoint v1 — to be implemented
    (survivorship.py)              # Strategy registry — to be implemented
    (temporal_distribution.py)     # Strategy registry — to be implemented
    (viewpoint_config.py)          # Frozen dataclass — to be implemented
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| Viewpoint | An opinionated materialized view: one perspective on consolidated data, produced by explicit rules |
| Builder | Source-specific function that reads a consolidated store and writes a viewpoint Parquet |
| Survivorship strategy | Pluggable rule for choosing between versions of the same event (decorator-registered, OCP) |
| Temporal distribution strategy | Pluggable rule for distributing summary events across months (decorator-registered, OCP) |
| ViewpointConfig | Frozen dataclass declaring which strategies to apply, which fields to select, which version tag |

## Invariants

- **Rebuildable:** A viewpoint can be deleted and rebuilt from the consolidated store at any time. This is normal operation, not error recovery.
- **Pure function:** Output = f(consolidated store, configuration). No hidden state.
- **Versioned:** Each viewpoint configuration has a version tag. Multiple versions coexist.
- **Provenance:** Every build writes a ledger entry: consolidated store digest + config version → output digest.
- **Fail-loud:** Build failures are logged and raised (ADR-008). No silent fallbacks.
- **No data invention:** A viewpoint must not contain information absent from the consolidated store.
