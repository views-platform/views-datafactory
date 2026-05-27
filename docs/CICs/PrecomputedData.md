# Class Intent Contract: PrecomputedData

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-05-27
**Related ADRs:** ADR-024, ADR-035

---

## 1. Purpose

> Precomputed state container for V-Dem grid verification: holds all derived arrays, indices, and metadata needed by 15 verification plots, computed in a single pass over the memory-mapped grid.

`PrecomputedData` is the central data structure in `scripts/verify_vdem_grid.py`. The `precompute()` function reads the compiled V-Dem grid once and populates all fields. Plot functions receive a `PrecomputedData` instance and extract what they need without re-reading the grid.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** perform verification (that is the job of the 15 `plot_*` functions)
- This class does **not** validate grid correctness (it reports what it finds; the plots interpret it)
- This class does **not** write any files
- This class does **not** modify the grid array
- This class does **not** handle GAUL crosswalk loading (that is done inside `precompute()` before construction)

---

## 3. Responsibilities and Guarantees

- **Per-feature last_valid_t:** `country_values` is NOT extracted at a single time step. Each feature uses its own last valid time step. For 18 main features this is the last time step in the grid; for 4 exclusion features (v2xpe_exl*) this is an earlier time step (Dec 2023 in V-Dem v16). The per-feature time step is determined by scanning backward from `last_valid_t` to find the first non-all-NaN slice.
- **Country deduplication:** `country_values` and `country_values_t0` contain one representative cell per country (the first cell in the GAUL crosswalk for that ISO3 code). All cells within a country have identical values (broadcast invariant, ADR-024 Invariant 6), so any cell is representative.
- **Single-pass construction:** All fields are derived from the grid in one call to `precompute()`. No field is lazily computed or updated after construction.
- **Read-only grid access:** The `grid` field is a memory-mapped numpy array opened in read-only mode (`mmap_mode="r"`). No field in this class writes to the grid.
- **Ocean mask consistency:** `ocean_mask` is derived from the liberal democracy index at `last_valid_t`. Cells that are NaN at this time step are considered ocean/unmapped. All plots use this same mask.

---

## 4. Inputs and Assumptions

| Field | Type | Description |
|-------|------|-------------|
| `grid` | `np.ndarray` | Memory-mapped [T, H, W, C] grid (read-only) |
| `features` | `list[str]` | Feature names from `feature_names.json` |
| `n_t`, `n_h`, `n_w`, `n_f` | `int` | Grid dimensions (time, height, width, features) |
| `ocean_mask` | `np.ndarray` | [H, W] boolean — True for ocean/unmapped cells |
| `dates` | `list[dt.date]` | One date per time step (first of each month) |
| `start_year` | `int` | Calendar year of the first time step |
| `libdem_idx` | `int` | Feature index for `vdem_v2x_libdem` |
| `last_valid_t` | `int` | Last time step with non-NaN libdem data |
| `latest_libdem` | `np.ndarray` | [H, W] libdem values at `last_valid_t` |
| `mean_libdem` | `np.ndarray` | [H, W] temporal mean of libdem |
| `nan_mask` | `np.ndarray` | [H, W] boolean — True where libdem is NaN at `last_valid_t` |
| `monthly_mean` | `np.ndarray` | [T] monthly global mean of libdem |
| `monthly_coverage` | `np.ndarray` | [T] monthly count of non-NaN libdem cells |
| `top_rows` | `np.ndarray` | Row indices of highest libdem-variance cells |
| `top_cols` | `np.ndarray` | Column indices of highest libdem-variance cells |
| `top_ts` | `np.ndarray` | [T] variance time series for top cells |
| `checks` | `dict[str, bool \| str]` | Automated check results (values_in_range, coverage_adequate, etc.) |
| `country_values` | `np.ndarray` | [n_countries, n_features] at each feature's last valid t |
| `country_values_t0` | `np.ndarray` | [n_countries, n_features] at earliest time step |
| `country_iso3` | `list[str]` | Sorted ISO3 codes for country dimension |
| `country_cells` | `dict[str, list[tuple[int, int]]]` | ISO3 → list of (row, col) grid cells |

**Assumptions:**
- `grid` has exactly 4 dimensions in [T, H, W, C] order (ADR-024 Invariant 1)
- `features` length matches `grid.shape[3]`
- `vdem_v2x_libdem` is present in `features` (used as the reference feature)
- GAUL `iso3_code.parquet` is available at `data/raw/gaul_admin/iso3_code.parquet` for country-level fields; if missing, country fields are empty and country-level plots are skipped

---

## 5. Outputs and Side Effects

- No side effects. Pure data container populated by `precompute()`.
- Country-level fields (`country_values`, `country_values_t0`, `country_iso3`, `country_cells`) may be empty arrays/lists if the GAUL crosswalk is unavailable. Plot functions check for this and skip gracefully.

---

## 6. Failure Modes and Loudness

- **Missing GAUL crosswalk:** `_load_country_map()` checks file existence and returns an empty mapping. Country-level plots skip with a warning. Not a crash.
- **Missing libdem feature:** `ValueError` from `features.index("vdem_v2x_libdem")`. Immediate crash — the reference feature is required.
- **All-NaN feature:** `last_valid_t` scan finds no non-NaN slice. Feature's `feat_last` defaults to `last_valid_t`. The feature appears in plots but with NaN values throughout.
- **Empty grid (0 time steps):** Would cause index errors in `precompute()`. Not guarded — the compilation step guarantees non-empty grids.

---

## 7. Boundaries and Interactions

- Defined in `scripts/verify_vdem_grid.py` (script-level, not a library)
- Constructed exclusively by `precompute()` in the same file
- Consumed by 15 `plot_*` functions and 1 `print_summary()` function in the same file
- Must not depend on any `datafactory_*` package (scripts are consumers, not library code)
- Reads from compiled grid files (npy) and GAUL crosswalk (parquet) — does not write

---

## 8. Examples of Correct Usage

```python
grid = np.load("data/compiled/vdem/grid.npy", mmap_mode="r")
features = json.loads(Path("data/compiled/vdem/feature_names.json").read_text())
start_year = 1980

d = precompute(grid, features, start_year)

# Pass to any plot function
plot_libdem_map(d, Path("reports/audit_vdem"))
plot_coverage_heatmap(d, Path("reports/audit_vdem"))

# Access country-level data at each feature's own last valid t
for i, iso3 in enumerate(d.country_iso3):
    libdem = d.country_values[i, d.libdem_idx]
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: Assuming all features share the same last valid time step
vals_at_t = grid[d.last_valid_t, :, :, :]  # exclusion features are NaN here

# WRONG: Mutating the grid through PrecomputedData
d.grid[0, 0, 0, 0] = 999.0  # mmap is read-only, raises ValueError

# WRONG: Using country_values without checking if country data was loaded
print(d.country_values.shape)  # may be (0, 0) if GAUL crosswalk missing
```

---

## 10. Test Alignment

- **Green:** Construction via `precompute()`, field types, ocean mask shape
- **Beige:** Missing libdem feature → ValueError, empty GAUL crosswalk → graceful skip
- **Red:** Per-feature last_valid_t correctness (exclusion features at earlier t than main features), broadcast invariant (within-country std == 0)

Reference test: `tests/test_falsification_vdem_audit_docs.py::TestP1PrecomputedDataCIC`.

---

## End of Contract

This document defines the **intended meaning** of `PrecomputedData`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
