# datafactory_harvester -- Architecture

## Purpose

Data ingestion framework with pluggable sources. Follows the pattern: config -> fetch -> validate -> store -> provenance. Raw data is stored unaltered -- no transformation at fetch time. This is a Source Node in the graph architecture (ADR-001) and a Layer 1 package in the dependency DAG (ADR-002).

## Responsibility Boundary

**Owns:**
- Data fetching from external APIs (UCDP/GED now, ACLED and others later)
- Schema validation of fetched data (required fields, types, domain constraints)
- Raw data storage as Parquet snapshots (verbatim, all fields preserved)
- Snapshot comparison (new vs. previous: added, removed, revised events)
- Provenance ledger entries for each harvest operation
- Source plugin registry

**Does NOT own:**
- Grid coordinate generation or spatial alignment (datafactory_grid)
- Event-to-grid compilation (datafactory_compiler)
- Data transformation or aggregation (stored raw)
- Consumer-specific formatting (no knowledge of downstream models)
- Synthetic data generation (datafactory_synthetic)
- Audit report generation (planned, not yet implemented)

## Dependency Rules

**May import:** `datafactory_core`, requests, pyarrow
**Must never import:** `datafactory_grid`, `datafactory_compiler`, `datafactory_synthetic`, or any consumer

## Package Structure

```
datafactory_harvester/
    __init__.py          -- public API exports
    validation.py        -- ValidationResult, ComparisonResult, validate_events, compare_snapshots
    storage.py           -- save_event_snapshot, archive_snapshot
    sources/
        __init__.py      -- source registry (register_source, fetch_source, list_sources)
        ucdp_annual.py   -- UCDP/GED Annual: config, API client, schema, fetch orchestrator
        ucdp_candidate.py -- UCDP/GED Candidate Monthly: version discovery, digest caching, multi-version fetch
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| ValidationResult | Schema validation outcome: n_events, warnings, errors, schema_snapshot, content_digest. Source-agnostic. |
| ComparisonResult | Revision detection between snapshots: n_added, n_removed, n_revised, total_revision_magnitude. Source-agnostic. |
| validate_events | Validates events against injected schema (required_fields, field_types). Uses `datafactory_core.compute_content_digest`. |
| compare_snapshots | Compares new events against previous Parquet snapshot. Injected id_field and key_fields. |
| save_event_snapshot | Parquet persistence of raw events with snappy compression. All source fields preserved. |
| Source registry | Dict-based registry. Sources auto-register on import. `fetch_source("ucdp_annual")` dispatches to the right function. |
| UcdpAnnualConfig | Frozen dataclass with `__post_init__` validation. Harvest-only params (no report params). |

## Source Plugin Pattern

Each data source lives in `sources/` as its own module. The shared skeleton provides:
- `validation.py`: validate_events (accepts schema as params), compare_snapshots (accepts id_field/key_fields)
- `storage.py`: save_event_snapshot, archive_snapshot
- `sources/__init__.py`: register_source, fetch_source

Each source module provides:
- Config (frozen dataclass with `__post_init__`)
- API client (fetch logic, pagination, retry)
- Schema contract (REQUIRED_FIELDS, FIELD_TYPES)
- Orchestrator (fetch -> validate -> compare -> store -> provenance)

Adding a new source means adding `sources/<name>.py`. No changes to existing sources.

## Invariants

- Raw data is stored unaltered (all source fields preserved in Parquet)
- Content digest (via `datafactory_core.compute_content_digest`) on every harvest
- Schema validation on every fetch -- fail-loud on missing required fields (ADR-003)
- Provenance ledger entry appended for every harvest operation, success or failure (ADR-008)
- Sources are independent: no source module imports from another source module
- Digest-based short-circuit: if snapshot exists and ledger has a digest, skip fetch
- All error paths log before raising (ADR-008)

## Intent Contracts

No formal CICs yet. Priority candidates when formalizing:
- `UcdpAnnualConfig` -- governs UCDP annual harvest parameters
- `ValidationResult` -- structured validation outcome
- `ComparisonResult` -- structured revision detection outcome
