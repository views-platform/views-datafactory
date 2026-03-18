# datafactory_compilation -- Architecture

## Purpose

Compilation edge -- reads source data (Parquet from harvester, npy from synthetic) and grid definition, produces compiled npy arrays with shape `(n_cells, n_steps, n_features)` plus coordinate metadata and provenance. This is the only Layer 2 package in the dependency DAG (ADR-002): it imports from core and grid, and reads harvester/synthetic output as files.

## Responsibility Boundary

**Owns:**
- Reading source data files (Parquet snapshots) from disk
- Placing events onto the spatiotemporal grid (event-to-cell assignment via `latlon_to_pgid`)
- Aggregating events per cell-month using declared strategy
- Producing compiled npy output with sidecar coordinate arrays
- Computing and recording source + output digests for provenance

**Does NOT own:**
- Data fetching or API interaction (datafactory_harvester)
- Grid definition or coordinate generation (datafactory_priogrid, but imports its configs)
- Synthetic data generation (datafactory_synthetic)
- Source-specific parsing logic (reads generic Parquet columns declared in config)
- Consumer-specific post-processing (consumers read compiled output as files)

## Dependency Rules

**May import:** `datafactory_provenance`, `datafactory_priogrid` (for GridConfig, TemporalConfig, coordinate arrays), numpy, pyarrow
**Must never import:** `datafactory_harvester`, `datafactory_synthetic`, or any consumer
**Data coupling:** Reads harvester/synthetic output as FILES on disk. The filesystem is the decoupling boundary (ADR-002).

## Package Structure

```
datafactory_compilation/
    __init__.py        -- public API: CompilationConfig, compile_grid, get_strategy
    compilation_config.py -- CompilationConfig (frozen, validated)
    aggregation.py -- built-in aggregation functions (count, sum_best, max_best) + registry
    grid_compilation.py -- compile_grid (main function), event placement, aggregation
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| CompilationConfig | Frozen dataclass: source path, grid/temporal configs, feature specs (name + strategy pairs), output dir, column mappings. Validated in `__post_init__`. |
| Aggregation strategies | Plain functions `list[dict] -> float` registered by name in `strategies.py`. Built-in: `count`, `sum_best`, `max_best`. Adding a strategy means adding a function (OCP). |
| compile_grid | Main function: reads Parquet -> places events via `latlon_to_pgid` -> aggregates per (cell, month) -> writes npy + sidecars + provenance. Deterministic. |
| FeatureSpec | Tuple of `(feature_name, strategy_name)`. Declared in config, never inferred from Parquet columns (ADR-003). |

## Invariants

- **Dimension order:** Always `(n_cells, n_steps, n_features)` -- the zarr-ready contract
- **Coordinate sidecars:** `pgids.npy` (int32), `time_steps.npy` (datetime64[M]), `feature_names.json` always shipped alongside `grid.npy`
- **Deterministic:** Same inputs + same config = bit-identical output + identical SHA-256 digest (NF-2)
- **Source digest computed:** SHA-256 of source file bytes computed and recorded in provenance (not cross-checked against an existing ledger -- the compiler records, it does not verify)
- **Feature list declared:** Features come from CompilationConfig, never inferred from Parquet columns (ADR-003)
- **Provenance entry:** Written for every compilation, linking source digest + output digest
- **Column mapping is source-agnostic:** The compiler reads lat/lon/date columns declared in config, not hardcoded field names. Built-in aggregation strategies (`sum_best`, `max_best`) reference the `best` field by convention — add source-specific strategies in `strategies.py` as needed (OCP)
- **All error paths log before raising** (ADR-008)

## Intent Contracts

No formal CICs yet. Priority candidate:
- `CompilationConfig` -- governs compilation behavior, feature declarations, column mappings
