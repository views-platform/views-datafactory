# datafactory_harvester -- Architecture

## Purpose

Data ingestion framework with pluggable sources. Follows the pattern: config -> fetch -> validate -> store -> provenance. Raw data is stored unaltered -- no transformation at fetch time. This is a Source Node in the graph architecture (ADR-001) and a Layer 1 package in the dependency DAG (ADR-002).

**Migration source:** `lab_harvester/` in views-metric-lab (1,629 LOC) + `lab_harvester_candidate/` (1,542 LOC).

## Responsibility Boundary

**Owns:**
- Data fetching from external APIs (UCDP/GED now, ACLED and others later)
- Schema validation of fetched data (required fields, types, domain constraints)
- Raw data storage as Parquet snapshots (verbatim, all fields preserved)
- Content digest computation for revision detection (SHA-256)
- Snapshot comparison (new vs. previous: added, removed, revised events)
- Provenance ledger entries for each harvest operation
- Audit report generation (Markdown + PNG)

**Does NOT own:**
- Grid coordinate generation or spatial alignment (datafactory_grid)
- Event-to-grid compilation (datafactory_compiler)
- Data transformation or aggregation (stored raw)
- Consumer-specific formatting (no knowledge of downstream models)
- Synthetic data generation (datafactory_synthetic)

## Dependency Rules

**May import:** `datafactory_core`, requests, pyarrow, matplotlib (reports), numpy
**Must never import:** `datafactory_grid`, `datafactory_compiler`, `datafactory_synthetic`, or any consumer

## Key Concepts

| Concept | Origin (metric lab) | Description |
|---------|---------------------|-------------|
| HarvesterConfig | `lab_harvester/config.py` | Frozen dataclass: dataset identity (name, version, year range), API transport (base_url, page_size, retries), paths. |
| UCDP API client | `lab_harvester/ucdp.py` | Paginated fetch with retry logic. Schema definition: 12 core required fields, ~49 total fields. Type validation per field. |
| ValidationResult | `lab_harvester/validation.py` | Schema validation outcome: n_events, warnings, errors, schema_snapshot, content_digest. |
| ComparisonResult | `lab_harvester/validation.py` | Revision detection between snapshots: n_added, n_removed, n_revised, total_revision_magnitude. |
| save_event_snapshot | `lab_harvester/validation.py` | Parquet persistence of raw events with snappy compression. All ~49 fields preserved. |
| audit report | `lab_harvester/report.py` | Markdown + PNG: events per year, fatality distribution, zero inflation, country ranking, revision summary. |

## Source Plugin Pattern

Each data source lives in `sources/` subdirectory as its own module. The shared harvester skeleton handles the common pattern:

1. Load source-specific config
2. Fetch data via source-specific API client
3. Validate against source-specific schema contract
4. Store raw Parquet snapshot
5. Compute content digest
6. Compare with previous snapshot (if exists)
7. Append provenance ledger entry
8. Generate audit report

Adding a new source means adding a new module in `sources/` with:
- API client (fetch logic, pagination, retries)
- Schema contract (required fields, type mapping, domain constraints)
- Config extension (source-specific parameters)

No changes to existing sources, the grid, or the compiler.

## Invariants

- Raw data is stored unaltered (all source fields preserved in Parquet)
- Content digest (SHA-256) computed on every harvest
- Schema validation on every fetch -- fail-loud on missing required fields (ADR-003)
- Provenance ledger entry appended for every harvest operation, success or failure
- Sources are independent: no source module imports from another source module
- Digest-based short-circuit: if content hasn't changed (digest match), skip expensive reporting
- Parquet snapshots use snappy compression

## CIC Stubs

### HarvesterConfig
**Purpose:** Immutable configuration governing a single harvest operation: what to fetch, from where, with what parameters.
**Non-goals:** Does not perform fetching. Does not validate data. Does not write provenance.
**Key guarantees:** Frozen after construction. `__post_init__` validates: start_year <= end_year, page_size > 0, max_retries >= 0, version non-empty, base_url non-empty. Serializable for provenance snapshots.

### ValidationResult
**Purpose:** Structured outcome of schema and domain validation for a fetched dataset.
**Non-goals:** Does not fetch data. Does not store data. Does not decide what to do about validation failures (caller decides).
**Key guarantees:** Contains: event count, list of warnings, list of errors, schema snapshot (field names + types), content digest. Immutable after construction. Errors list non-empty means validation failed.
