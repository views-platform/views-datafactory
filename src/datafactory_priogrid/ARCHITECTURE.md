# datafactory_priogrid -- Architecture

## Purpose

PRIO-GRID spatial backbone and temporal backbone. Defines the shared coordinate system that all compiled data aligns to: 259,200 cells at 0.5 degree resolution, monthly time steps from 1989 to 2024. Pure numpy with zero external data dependencies for grid generation. This is a Layer 1 package in the dependency DAG (ADR-012).

**Migration source:** `lab_grid/` in views-metric-lab (868 LOC).

## Responsibility Boundary

**Owns:**
- Spatial grid definition (PRIO-GRID: 360 rows x 720 columns, 0.5 deg, row-major from bottom-left, 1-indexed pgids)
- Temporal backbone definition (monthly, 1989-2024, VIEWS month_id adapter)
- Composed spatiotemporal grid (GridConfig + TemporalConfig)
- Coordinate array generation (pgids, latitudes, longitudes, time steps)
- Parity validation against PRIO reference shapefile (one-time)
- Pluggable shapefile reader via Protocol (DIP)

**Does NOT own:**
- Data values (no event counts, fatalities, or features)
- Source-specific logic (no UCDP, no ACLED)
- Compilation (no event-to-grid placement)
- Consumer formatting (no model-specific output)
- Provenance tracking (uses core's utilities)

## Dependency Rules

**May import:** `datafactory_provenance`, numpy, pyshp (shapefile reader only)
**Must never import:** `datafactory_harvester`, `datafactory_compilation`, `datafactory_synthetic`, or any consumer

## Key Concepts

| Concept | Description |
|---------|-------------|
| GridConfig | Frozen dataclass: resolution, bounds, CRS. Validated in `__post_init__`. Default: 0.5 deg, global extent, 360x720 grid. |
| TemporalConfig | Frozen dataclass: start/end year and month. Validates range constraints. VIEWS month_id adapter (month_id 1 = January 1980). |
| SpatioTemporalGrid | Composes GridConfig + TemporalConfig. Lazy coordinate generation via `cached_property`. |
| generate_grid | Pure numpy: generates pgid array, bounding box arrays, lat/lon coordinate arrays. |
| generate_time_steps | Generates `datetime64[M]` array. Converts to/from VIEWS month_id. |
| ReferenceGeometryReader | Protocol for pluggable shapefile readers. Decouples validation from pyshp. |
| validate_parity | Validates generated grid against PRIO reference shapefile. Records result to provenance ledger. |
| land_mask | Fetches land cell pgids from PRIO-GRID API (`landarea` variable, 64,818 cells). Cached to disk. Not auto-imported (avoids pulling `requests`). |

## Invariants
- **Single-writer access assumed.** No concurrent operations supported (see concerns00.md C-16)

- Default configuration produces exactly 259,200 cells (360 x 720)
- pgid numbering: row-major from bottom-left, 1-indexed (pgid 1 is southwest corner)
- Temporal backbone uses VIEWS month_id convention: month_id = (year - 1980) * 12 + month
- Grid resolution must evenly divide the spatial extent (validated in `__post_init__`)
- start_year <= end_year (validated in `__post_init__`)
- Coordinate arrays are generated lazily but are deterministic
- Pure numpy: no heavy geospatial libraries (NF-6)

## Intent Contracts

Formal CICs for this module's non-trivial classes:

- [GridConfig](../../docs/CICs/GridConfig.md)
- [TemporalConfig](../../docs/CICs/TemporalConfig.md)
- [SpatioTemporalGrid](../../docs/CICs/SpatioTemporalGrid.md)
- [ShapefileHarvesterConfig](../../docs/CICs/ShapefileHarvesterConfig.md)
