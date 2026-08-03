
# ADR-024: Compilation Grid Invariants

**Status:** Accepted
**Date:** 2026-04-08
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Applies:** ADR-012 (Four-Layer Data Architecture)

---

## Context

The compilation layer (Layer 4) transforms viewpoint event tables into fixed-shape numpy arrays on the PRIO-GRID. A configuration audit (April 2026) identified decisions that are now configurable (output_dtype, fill_value, FeatureSpec.value_field) and decisions that must remain fixed as architectural invariants of the grid format.

---

## Decision

The following 6 architectural invariants define the physical layout of the output array and cannot be changed without breaking all downstream consumers (zarr export, dataframe adapter, FeatureFrame adapter, model training scripts). Invariants 1–5 apply to all compiled grids; Invariant 6 applies only to country-level sources.

### 1. Grid Dimension Order: [T, H, W, C]

Output arrays have shape `(time_steps, height, width, channels)`:
- Axis 0: time (months, earliest first)
- Axis 1: height (grid rows, south to north)
- Axis 2: width (grid columns, west to east)
- Axis 3: channels (features, in `config.features` declaration order)

### 2. Spatial Binning: Floor-Based Cell Assignment

Events are assigned to grid cells using `latlon_to_pgid()`, which uses floor-based assignment:

```python
row = floor((lat - south) / resolution)
col = floor((lon - west) / resolution)
```

Points exactly on a cell boundary are assigned to the cell to the south-west. Points outside the grid bounds are clamped to the nearest valid cell.

### 3. Temporal Binning: Month Precision

Dates are parsed as ISO-8601 date strings (year-month-day). Only the year and month are used for bin assignment. The day component is ignored. Events are assigned to a 0-based month index relative to `config.temporal_config.start_year/start_month`.

Events outside the configured temporal range are silently skipped (logged as warnings).

### 4. Feature Stacking Order: Declaration Order

Feature channel 0 corresponds to `config.features[0]`, channel 1 to `config.features[1]`, etc. Consumers must read the `feature_names.json` sidecar to know which channel is which.

### 5. Per-Feature Filter Semantics: AND Logic

When a `FeatureSpec` has a non-empty `filter` dict, all conditions must be satisfied (AND semantics). There is no OR or NOT support.

### 6. Country-Level Broadcast

**Applies to:** Pregridded (country-level) sources only (V-Dem, future WDI).

For sources that provide country-level data (not cell-level), all PRIO-GRID cells within the same country must have identical values at every time step for every feature. Within-country standard deviation must be exactly zero.

**Rationale:** Country-level sources like V-Dem provide one value per country-year. The viewpoint builder broadcasts this value to all cells in the country via the GAUL ISO3→pgid crosswalk. If the broadcast is incorrect (e.g., off-by-one in pgid mapping, partial crosswalk update), neighboring country values would bleed into each other — a spatial data corruption that would be invisible in country-level analysis but produce wrong cell-level model inputs.

**Verification:** `scripts/verify_vdem_grid.py`, Plot 14 (Broadcast Integrity). Computes within-country standard deviation for all features at the latest valid time step. PASS if all values are exactly 0.0.

**Not applicable to:** Event-based sources (UCDP, ACLED) where cell values differ by construction. Raster sources (GHS-POP, GHS-BUILT-S) where cell values vary spatially within countries.

### PGID Convention

PRIO-GRID cell IDs (`pgid`) are 1-indexed. This convention applies to all grid operations (spatial binning, event compilation, raster placement, country-level broadcast).

- **Forward (coordinates → pgid):** `pgid = row * 720 + col + 1` where `row = 0..359` (south to north), `col = 0..719` (west to east).
- **Inverse (pgid → grid indices):** `row = (pgid - 1) // 720`, `col = (pgid - 1) % 720`.

The 1-indexed convention means `pgid` ranges from 1 to 259,200. Grid arrays use 0-indexed `[row, col]`. The `- 1` in the inverse formula accounts for this offset. Omitting it shifts all spatial data one cell east and wraps the last column.

**Authoritative source:** `generate_grid()` in `src/datafactory_priogrid/cell_generator.py`.

---

## Rationale

- **[T, H, W, C] order:** Matches numpy/xarray conventions for spatiotemporal data. Time-first layout enables efficient temporal slicing (the most common access pattern for forecasting).
- **Floor-based assignment:** Matches PRIO-GRID's standard cell numbering convention. Changing this would misalign with all PRIO-GRID consumers.
- **Month precision:** VIEWS operates at monthly resolution. Sub-monthly precision would create 30x more bins without research value.
- **Declaration order:** Explicit ordering via config avoids surprising behavior from sorted or hash-based ordering.

---

## Consequences

### Positive

- All consumers can rely on a stable physical layout.
- Coordinate sidecar files (`pgids.npy`, `time_steps.npy`, `feature_names.json`) provide metadata needed to interpret the grid without external documentation.

### Negative

- Adding sub-monthly resolution would require a new compiler, not a configuration change.
- OR/NOT filter logic would require extending FeatureSpec, not just adding a new filter dict.

---

## Validation & Monitoring

- `tests/test_compiler.py::TestCompileGridGreen::test_produces_correct_shape` verifies [T, H, W, C] layout.
- `tests/test_compiler.py::TestCompileGridBoundaryBeige` tests spatial binning edge cases.
- Feature order is verified by comparing `feature_names.json` against the config declaration.

---

## References

- `src/datafactory_compilation/grid_compilation.py` — the compiler
- `src/datafactory_priogrid/cell_generator.py` — spatial binning implementation
- ADR-010 (GridConfig spatial-only) — grid geometry decisions
