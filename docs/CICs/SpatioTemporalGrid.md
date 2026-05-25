# Class Intent Contract: SpatioTemporalGrid

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-03-20
**Related ADRs:** ADR-001, ADR-012

---

## 1. Purpose

> Composed spatiotemporal index that pairs a spatial grid (GridConfig) and temporal range (TemporalConfig), lazily generating coordinate arrays for downstream data cubes.

This is the index that compiled grids and ExperimentFrames align to.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** contain data values (event counts, fatalities, features)
- This class does **not** perform compilation or event-to-grid placement
- This class does **not** depend on any specific data source
- This class does **not** modify its composed configs (delegation, not duplication)

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Guarantees composition by delegation: delegates `n_cells` to `grid_config.n_cells`, `n_steps` to `temporal_config.n_steps`
- Guarantees lazy, cached coordinate generation via `functools.cached_property`
- Guarantees consistency between coordinate arrays and config dimensions
- Provides `shape` as `(n_cells, n_steps)` for data cube alignment

---

## 4. Inputs and Assumptions

- `grid_config`: a valid `GridConfig` (default: standard PRIO-GRID)
- `temporal_config`: a valid `TemporalConfig` (default: 1989-2026)

Both configs are validated at their own construction time. SpatioTemporalGrid does not re-validate them.

---

## 5. Outputs and Side Effects

- `pgids`: 1-D int32 array of cell IDs, length `n_cells` (e.g., 259,200 for standard PRIO-GRID). Lazily generated, cached.
- `lats`, `lons`: 1-D float64 arrays of cell centroid coordinates, length `n_cells`. Lazily generated, cached.
- `time_steps`: 1-D datetime64[M] array (lazily generated, cached)
- `shape`: tuple `(n_cells, n_steps)`
- No side effects beyond caching.

**Caching mechanism:** The spatial arrays (`pgids`, `lats`, `lons`) are produced by `generate_grid()` which returns three 1-D arrays of length `n_cells`. These are cached together via `functools.cached_property` on `_spatial_arrays`. The public attributes `pgids`, `lats`, and `lons` are `@property` accessors that delegate to `_spatial_arrays`, so all three are computed and cached on first access to any one of them.

---

## 6. Failure Modes and Loudness

- Invalid configs are caught at config construction time, not here
- `AttributeError` on mutation attempt (frozen)
- No silent failures possible — all coordinate generation is deterministic numpy

---

## 7. Boundaries and Interactions

- Composes `GridConfig` and `TemporalConfig` as peers (neither is subordinate)
- Calls `generate_grid` and `generate_time_steps` for lazy coordinate generation
- May be consumed by any downstream module that needs the index
- Must not depend on harvester or compiler modules

---

## 8. Examples of Correct Usage

```python
grid = SpatioTemporalGrid()  # Standard: 259,200 cells x 456 months
grid.shape  # (259200, 456)
grid.pgids  # lazily generated on first access
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: storing data in the grid object
grid.data = my_array  # AttributeError — frozen

# WRONG: assuming grid generates data
values = grid.compile(events)  # No such method — compilation is separate
```

---

## 10. Test Alignment

- **Green:** Shape matches config dimensions, coordinate arrays consistent with configs
- **Beige:** Not directly tested in isolation (tested through generate_grid and config tests)
- **Red:** Mutation attempt (frozen enforcement)

Tests in `tests/test_grid.py` (indirectly via generate_grid and config tests).

---

## End of Contract

This document defines the **intended meaning** of `SpatioTemporalGrid`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
