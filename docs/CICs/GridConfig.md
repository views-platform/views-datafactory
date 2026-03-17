# Class Intent Contract: GridConfig

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-03-17
**Related ADRs:** ADR-001, ADR-009

---

## 1. Purpose

> Immutable spatial grid configuration defining resolution, bounding box, and coordinate reference system for the PRIO-GRID.

Default values reproduce the standard PRIO-GRID: 360 rows x 720 columns of 0.5 x 0.5 degree cells covering the full globe (259,200 cells).

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** store filesystem paths (data directories, provenance directories)
- This class does **not** store remote URLs (shapefile download locations)
- This class does **not** generate coordinate arrays (that is `generate_grid`)
- This class does **not** store data values or temporal information
- This class does **not** know about consumers or compilation formats

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Guarantees all spatial parameters are valid after construction (`__post_init__` validation)
- Guarantees resolution is positive
- Guarantees west < east and south < north
- Guarantees resolution evenly divides both lat and lon extents
- Provides derived dimensions as properties: `nrow`, `ncol`, `n_cells`

---

## 4. Inputs and Assumptions

- `resolution`: float, positive, must evenly divide spatial extents
- `west`, `east`: float, west < east (WGS84 longitude)
- `south`, `north`: float, south < north (WGS84 latitude)
- `crs`: string, coordinate reference system identifier

Assumptions not met cause immediate `ValueError`.

---

## 5. Outputs and Side Effects

- No side effects. Pure configuration container.
- Properties `nrow`, `ncol`, `n_cells` are computed from stored fields.

---

## 6. Failure Modes and Loudness

- `ValueError` on resolution <= 0
- `ValueError` on inverted bounds (west >= east, south >= north)
- `ValueError` on indivisible resolution
- `AttributeError` on any attempt to mutate fields (frozen)

All failures are immediate and loud. No silent fallbacks.

---

## 7. Boundaries and Interactions

- May be imported by any `datafactory_*` package (via `datafactory_grid`)
- Used by `generate_grid`, `generate_bounding_boxes`, `pgid_to_latlon`, `latlon_to_pgid`
- Composed into `SpatioTemporalGrid`
- Must not depend on any other `datafactory_*` class

---

## 8. Examples of Correct Usage

```python
cfg = GridConfig()  # Standard PRIO-GRID: 259,200 cells
cfg = GridConfig(resolution=0.25)  # 4x finer: 1,036,800 cells
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: GridConfig should not have path fields
GridConfig(data_dir=Path("data"))  # TypeError — no such field

# WRONG: Inferring resolution from array shape
resolution = 180.0 / array.shape[0]  # Violates ADR-003
```

---

## 10. Test Alignment

- **Green:** Default cell count (259,200), custom resolution, derived properties
- **Beige:** Zero resolution, negative resolution, inverted bounds, indivisible resolution
- **Red:** Mutation attempt (frozen enforcement)

Tests in `tests/test_grid.py`.

---

## End of Contract

This document defines the **intended meaning** of `GridConfig`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
