# datafactory_compilation -- Architecture

## Purpose

Compilation edge -- reads viewpoint output (Parquet) and grid definition, produces compiled npy arrays with shape `[T, H, W, C]` (time, height, width, channels) plus coordinate metadata and provenance. This is a Layer 4 package in the dependency DAG (ADR-012): it imports from provenance and priogrid, and reads viewpoint output as files. Synthetic data follows an independent path and does not pass through compilation.

## Responsibility Boundary

**Owns:**
- Reading viewpoint output files (Parquet) from disk
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
**Must never import:** `datafactory_harvester`, `datafactory_consolidation`, `datafactory_viewpoint`, `datafactory_synthetic`, or any consumer
**Data coupling:** Reads viewpoint output as FILES on disk. The filesystem is the decoupling boundary (ADR-012).

## Package Structure

```
datafactory_compilation/
    __init__.py        -- public API: CompilationConfig, compile_grid, get_strategy
    compilation_config.py -- CompilationConfig (frozen, validated)
    aggregation.py -- built-in aggregation functions (count, sum_field, max_field) + registry
    grid_compilation.py -- compile_grid (main function), event placement, aggregation
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| CompilationConfig | Frozen dataclass: source path, grid/temporal configs, feature specs (name + strategy pairs), output dir, column mappings. Validated in `__post_init__`. |
| Aggregation strategies | Plain functions `(list[dict], str) -> float` registered by name. Built-in: `count`, `sum_field`, `max_field`. The second argument is the event field name to aggregate (configurable via `FeatureSpec.value_field`). `sum_best`/`max_best` are backward-compatible aliases. Adding a strategy means adding a function (OCP). |
| compile_grid | Main function: reads Parquet -> places events via `latlon_to_pgid` -> aggregates per (cell, month) -> writes npy + sidecars + provenance. Deterministic. |
| FeatureSpec | Frozen dataclass: `name`, `strategy`, optional `filter` dict, `value_field` (default `"best"`). Filter enables per-feature disaggregation (e.g., `{"type_of_violence": 1}` for state-based only). `value_field` controls which event field is aggregated. Declared in config, never inferred (ADR-003). |

## Invariants
- **Single-writer access assumed.** No concurrent operations supported (see technical_risk_register_resolved.md C-16)

- **Dimension order:** Always `[T, H, W, C]` — time, height (rows), width (columns), channels (features). Canonical z-stack layout.
- **Coordinate sidecars:** `pgids.npy` (int32, shape `[H, W]`), `time_steps.npy` (datetime64[M]), `feature_names.json` always shipped alongside `grid.npy`
- **Deterministic:** Same inputs + same config = bit-identical output + identical SHA-256 digest (NF-2)
- **Source digest computed:** SHA-256 of source file bytes computed and recorded in provenance (not cross-checked against an existing ledger -- the compiler records, it does not verify)
- **Feature list declared:** Features come from CompilationConfig, never inferred from Parquet columns (ADR-003)
- **Provenance entry:** Written for every compilation, linking source digest + output digest
- **Column mapping is source-agnostic:** The compiler reads lat/lon/date columns declared in config, not hardcoded field names. The aggregation field is configurable via `FeatureSpec.value_field` (default `"best"`).
- **All error paths log before raising** (ADR-008)

## Intent Contracts

- `CompilationConfig` -- governs compilation behavior, feature declarations, column mappings (CIC at `docs/CICs/CompilationConfig.md`)
