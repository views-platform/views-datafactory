# datafactory_compiler -- Architecture

## Purpose

Compilation edge -- reads source data (Parquet from harvester, npy from synthetic) and grid definition, produces compiled npy arrays with shape `(n_cells, n_steps, n_features)` plus coordinate metadata and provenance. This is the only Layer 2 package in the dependency DAG (ADR-002): it imports from core and grid, and reads harvester/synthetic output as files.

**Migration source:** No existing implementation. This is new code informed by the product development plan and metric lab consumer requirements.

## Responsibility Boundary

**Owns:**
- Reading source data files (Parquet snapshots, synthetic npy) from disk
- Verifying source file integrity (digest match against provenance ledger)
- Placing events onto the spatiotemporal grid (event-to-cell assignment)
- Aggregating events per cell-month using declared strategy
- Producing compiled npy output with sidecar coordinate arrays
- Writing compilation provenance (source digests + config -> output digest)

**Does NOT own:**
- Data fetching or API interaction (datafactory_harvester)
- Grid definition or coordinate generation (datafactory_grid, but imports its configs)
- Synthetic data generation (datafactory_synthetic)
- Source-specific parsing logic (reads generic Parquet columns declared in config)
- Consumer-specific post-processing (consumers read compiled output as files)
- Model evaluation or metrics (metric lab's domain)

## Dependency Rules

**May import:** `datafactory_core`, `datafactory_grid` (for GridConfig, TemporalConfig, coordinate arrays), numpy
**Must never import:** `datafactory_harvester`, `datafactory_synthetic`, or any consumer
**Data coupling:** Reads harvester/synthetic output as FILES on disk. The filesystem is the decoupling boundary (ADR-002).

## Key Concepts

| Concept | Description |
|---------|-------------|
| CompilationConfig | Frozen dataclass: source references (paths + expected digests), feature list, aggregation strategy name, output path. Validated in `__post_init__`. |
| AggregationStrategy (Protocol) | Pluggable aggregation: count, sum_fatalities, max_severity, type_decomposition. Each strategy is a callable conforming to a declared interface. |
| compile_grid | Main function: reads source files + grid config -> produces npy + coordinate arrays + provenance JSON. Deterministic. |
| CompilationLedgerEntry | Provenance record: source file paths + digests, config hash, output path + digest, timestamp, validation results. |

## Invariants

- **Dimension order:** Always `(n_cells, n_steps, n_features)` -- the zarr-ready contract
- **Coordinate sidecars:** `pgids.npy` (int32), `time_steps.npy` (datetime64[M]), `feature_names.json` always shipped alongside `grid.npy`
- **Deterministic:** Same inputs + same config = bit-identical output + identical SHA-256 digest (NF-2)
- **Digest verification:** Source files must exist and their digest must match the provenance ledger before compilation proceeds (ADR-003)
- **Feature list declared:** Features come from CompilationConfig, never inferred from Parquet columns (ADR-003)
- **Provenance entry:** Written for every compilation, linking input digests + config hash to output digest
- **No source-specific code:** The compiler does not know about UCDP field names or synthetic generator parameters -- it reads generic columns declared in config
- **Performance:** Full grid compilation (259,200 cells x 432 months) under 60 seconds (NF-5)

## CIC Stubs

### CompilationConfig
**Purpose:** Immutable configuration governing a single compilation operation: which sources, which features, which aggregation strategy, where to write output.
**Non-goals:** Does not perform compilation. Does not fetch data. Does not define grid coordinates.
**Key guarantees:** Frozen after construction. `__post_init__` validates: all source paths non-empty, feature list non-empty, aggregation strategy is a recognized name, output path is non-empty. Source digests are declared (not looked up at config time). Serializable for provenance.

### AggregationStrategy (Protocol)
**Purpose:** Pluggable interface for aggregating events within a cell-month into a single feature value.
**Non-goals:** Does not read source files. Does not assign events to cells. Does not write output.
**Key guarantees:** Deterministic: same events in same order = same value. Declared input schema (which columns it reads). Declared output dtype (float32). Raises on unexpected input (missing columns, wrong types).
