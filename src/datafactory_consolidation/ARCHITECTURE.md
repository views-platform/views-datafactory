# datafactory_consolidation -- Architecture

## Purpose

Lossless consolidation of raw source snapshots into version-aware event stores. Combines multiple vintages (annual releases, candidate versions) from each data source into a single, append-only, queryable store with bitemporal metadata. This is a Layer 2 package in the dependency DAG (ADR-012) implementing the consolidation principles defined in ADR-013.

## Responsibility Boundary

**Owns:**
- Source-specific consolidation logic (one consolidator per data source)
- Append-only event store I/O (write new vintages, query by version/time)
- Bitemporal metadata: `_source_type`, `_source_version`, `_ingested_at`
- Lossless field preservation (no columns dropped)
- Provenance tracking for consolidation operations

**Does NOT own:**
- Data fetching or harvesting (datafactory_harvester — Layer 1)
- Survivorship decisions between versions (datafactory_viewpoint — Layer 3)
- Temporal distribution of summary events (datafactory_viewpoint — Layer 3)
- Grid placement or aggregation (datafactory_compilation — Layer 4)
- Choosing which version of an event is "right" (that is an opinion; opinions live in Layer 3)

## Dependency Rules

**May import:** `datafactory_provenance`
**Reads filesystem output of:** `datafactory_harvester` (Parquet snapshots in `data/`)
**Must never import:** `datafactory_priogrid`, `datafactory_harvester`, `datafactory_viewpoint`, `datafactory_compilation`, `datafactory_synthetic`, or any consumer

## Package Structure

```
datafactory_consolidation/
    __init__.py                    # Package docstring, empty __all__ until implementation
    ARCHITECTURE.md                # This file
    consolidators/
        __init__.py                # Registry: register_consolidator, consolidate_source, list_consolidators
        (ucdp.py)                  # UCDP consolidator — to be implemented
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| Consolidator | Source-specific function that reads raw snapshots and appends to a consolidated store |
| Consolidated store | Append-only Parquet containing all versions of all events with bitemporal metadata |
| Registry | Dict-based registry (mirrors harvester/sources pattern) — OCP: add consolidator = add file |

## Invariants

- **Lossless:** No source fields are dropped during consolidation. Metadata columns are added, never replacing source columns.
- **Append-only:** Existing records in the consolidated store are never modified or deleted.
- **Bitemporal:** Every record carries valid time (event dates) and transaction time (ingestion metadata).
- **Provenance:** Every consolidation operation writes a ledger entry with input/output digests.
- **Fail-loud:** Consolidation failures are logged and raised (ADR-008). No silent fallbacks.
