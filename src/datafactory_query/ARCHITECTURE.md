# datafactory_query -- Architecture

## Purpose

Consumer-facing query layer -- the primary entry point for training scripts and downstream consumers. Provides temporal subsetting, geographic filtering, and feature selection over assembled grids, returning data as FeatureFrame or DataFrame. Supports both local npy directories and remote zarr stores (HTTP with netrc auth). This package sits alongside the graph, not inside it: it reads assembled output as files and imports from priogrid + adapters.

## Responsibility Boundary

**Owns:**
- `load_dataset()` — unified consumer entry point with region, time, feature, and format parameters
- Region resolution — mapping region names ("Ethiopia", "africa_me", "land") to PRIO-GRID cell sets via GAUL Parquets
- Temporal parsing — flexible input (ISO strings, VIEWS month_ids, years) to datetime64[M] ranges
- Dual backend selection — npy (local, mmap) vs zarr (local or remote via fsspec/xarray)
- Lazy subsetting for zarr — time and feature slices applied before materializing, avoiding full-grid downloads
- Credential resolution — reading ~/.netrc for authenticated remote zarr access

**Does NOT own:**
- Grid compilation or event placement (datafactory_compilation)
- Grid assembly (scripts/assemble_grid.py)
- Viewpoint building or survivorship rules (datafactory_viewpoint)
- Data harvesting (datafactory_harvester)
- Consumer vocabulary translation (scripts/generate_consumer_data.py)

## Dependency Rules

**May import:** `datafactory_priogrid` (for GridConfig defaults), `datafactory_adapters` (for FeatureFrame, grid_to_dataframe, grid_to_feature_frame)
**Reads filesystem output of:** `scripts/assemble_grid.py` (assembled grid at `data/assembled/` or zarr store)
**Must never import:** `datafactory_harvester`, `datafactory_consolidation`, `datafactory_viewpoint`, `datafactory_compilation`, `datafactory_synthetic`

## Package Structure

```
datafactory_query/
    __init__.py        -- public API: load_dataset, list_regions, load_region_pgids, parse_time_range
    dataset.py         -- load_dataset (main function), dual npy/zarr backend, format conversion
    regions.py         -- region name → set of PRIO-GRID cell IDs (via GAUL Parquets)
    temporal.py        -- flexible time parsing: ISO, month_id, year → datetime64[M] range
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| `load_dataset()` | Unified entry point. Accepts region, time range, feature list, output format, and data path (npy dir or zarr URL). Returns FeatureFrame or DataFrame. |
| Dual backend | npy path loads via `np.load(mmap_mode="r")` (zero-copy, local only). Zarr path uses `xarray.open_zarr()` with lazy slicing (supports remote HTTP). Backend selected automatically by path suffix. |
| Region resolution | Predefined regions ("africa_me", "americas", "europe", "asia_oceania") plus any GAUL country name. Resolution uses GAUL Level 0/1/2 Parquet files to map names to PRIO-GRID cell sets. Cached after first load. |
| VIEWS month_id | Integer encoding: `(year - epoch) * 12 + month`. Default epoch is 1980. Temporal parsing accepts month_ids as integers alongside ISO date strings. |

## Invariants

- **Read-only:** Never modifies source data. All subsetting produces new arrays.
- **Lazy zarr subsetting:** For remote stores, time and feature slices are applied on the xarray Dataset before materializing. Only the requested subset is downloaded.
- **Fail-loud on missing data:** Raises `FileNotFoundError` if assembled grid or zarr store is not found. Raises `ValueError` for unknown features or invalid regions.
- **Format validation:** Only "feature_frame" and "dataframe" are valid output formats. Invalid format raises `ValueError`.
- **Credential warning:** If ~/.netrc lacks credentials for a remote zarr host, logs a warning before attempting unauthenticated access (may fail with 401).
- **Feature ordering (C-127):** The npy backend returns features in `feature_names.json` order. The zarr backend uses the `feature_order` dataset attribute if present; otherwise falls back to alphabetical (`sorted(ds.data_vars)`). Consumers must access features by name, not by position index. The zarr export should write `feature_order` to ensure backend parity.

## Intent Contracts

- None yet — this package has no frozen config dataclass requiring a CIC.
