# datafactory_grid -- Architecture

## Purpose

PRIO-GRID spatial backbone and temporal backbone. Defines the shared coordinate system that all compiled data aligns to: 259,200 cells at 0.5 degree resolution, monthly time steps from 1989 to 2024. Pure numpy with zero external data dependencies for grid generation. This is a Layer 1 package in the dependency DAG (ADR-002).

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

**May import:** `datafactory_core`, numpy, pyshp (shapefile reader only)
**Must never import:** `datafactory_harvester`, `datafactory_compiler`, `datafactory_synthetic`, or any consumer

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

## Invariants

- Default configuration produces exactly 259,200 cells (360 x 720)
- pgid numbering: row-major from bottom-left, 1-indexed (pgid 1 is southwest corner)
- Temporal backbone uses VIEWS month_id convention: month_id = (year - 1980) * 12 + month
- Grid resolution must evenly divide the spatial extent (validated in `__post_init__`)
- start_year <= end_year (validated in `__post_init__`)
- Coordinate arrays are generated lazily but are deterministic
- Pure numpy: no heavy geospatial libraries (NF-6)

## CIC Stubs

### GridConfig
**Purpose:** Immutable spatial grid configuration defining resolution, bounds, and coordinate reference system.
**Non-goals:** Does not generate coordinates (that's `generate_grid`). Does not store data values. Does not know about time.
**Key guarantees:** Frozen after construction. `__post_init__` validates resolution > 0, west < east, south < north, resolution evenly divides extent. Cell count is derivable: `n_rows * n_cols`.

### TemporalConfig
**Purpose:** Immutable temporal backbone configuration defining year range and month_id mapping.
**Non-goals:** Does not generate time step arrays (that's `generate_time_steps`). Does not know about spatial coordinates.
**Key guarantees:** Frozen after construction. `__post_init__` validates start_year <= end_year, months in [1, 12]. Step count is derivable: `(end_year - start_year) * 12 + (end_month - start_month) + 1`.

### SpatioTemporalGrid
**Purpose:** Composed spatiotemporal backbone providing coordinate arrays for both spatial and temporal dimensions.
**Non-goals:** Does not contain data values. Does not perform compilation. Does not depend on any specific data source.
**Key guarantees:** Lazy generation via `cached_property`. Coordinate arrays are consistent with GridConfig and TemporalConfig. Shape of coordinate arrays matches grid dimensions.
