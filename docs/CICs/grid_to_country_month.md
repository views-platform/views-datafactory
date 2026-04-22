# Class Intent Contract: grid_to_country_month

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-04-22
**Related ADRs:** ADR-012, ADR-025

---

## 1. Purpose

> Aggregates the canonical [T, H, W, C] grid array to a country-month DataFrame by summing feature values per (month_id, country_id) pair.

This is the bridge between grid-native data (one row per cell per month) and country-level analysis (one row per country per month). Uses a country identifier feature (default: `gaul0_code` per ADR-025) as the grouping key.

---

## 2. Non-Goals (Explicit Exclusions)

- This module does **not** perform feature engineering or transformations beyond summation
- This module does **not** apply temporal alignment or padding
- This module does **not** validate that the grid contains meaningful data (non-zero, non-NaN)
- This module does **not** know about specific country codes or their semantics
- This module does **not** handle weighted aggregation (area-weighted, population-weighted)

---

## 3. Responsibilities and Guarantees

- Guarantees that the output DataFrame has a `(month_id, country_id)` MultiIndex
- Guarantees that the country feature column is excluded from the output (it becomes the index)
- Guarantees that ocean cells (country_id <= 0) are excluded from aggregation
- Guarantees that aggregation is summation (groupby sum) — no averaging, no counting
- Guarantees `ValueError` if the specified country feature is not in `feature_names`
- Reuses `_flatten_grid()` from `grid_to_dataframe` for the initial flattening step

---

## 4. Inputs and Assumptions

- `grid`: numpy array of shape [T, H, W, C] — the assembled grid
- `pgids`: numpy array of shape [H, W] — cell ID array
- `time_steps`: numpy array of shape [T] — datetime64[M] timestamps
- `feature_names`: list of C strings — column names matching the C dimension
- `country_feature`: str, must exist in `feature_names` (default: `"gaul0_code"`)
- `land_pgids`: optional set of land cell IDs for filtering
- `month_id_epoch`: int, base year for month_id encoding (default: 0)

Assumptions not met cause immediate `ValueError`.

---

## 5. Outputs and Side Effects

- Returns a `pd.DataFrame` with `(month_id, country_id)` MultiIndex
- One column per feature except the country feature
- All values are sums over grid cells belonging to each (month, country) group
- No side effects. Pure function.

---

## 6. Failure Modes and Loudness

- `ValueError` if `country_feature` is not in `feature_names`
- Delegates to `_flatten_grid()` for shape mismatches

All failures are immediate and loud. No silent fallbacks.

---

## 7. Boundaries and Interactions

- Imports `_flatten_grid` from `datafactory_adapters.grid_to_dataframe` (same package)
- No `datafactory_*` imports outside `datafactory_adapters`
- Sits alongside the graph (adapters layer), not inside it
- Consumers: model scripts that need country-level aggregation

---

## 8. Examples of Correct Usage

```python
from datafactory_adapters.grid_to_country_month import grid_to_country_month

df = grid_to_country_month(
    grid, pgids, time_steps, feature_names,
    country_feature="gaul0_code",
)
# df.index: MultiIndex (month_id, country_id)
# df.columns: all features except gaul0_code
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: country_feature not in feature_names
grid_to_country_month(grid, pgids, ts, ["ged_sb_best"])
# ValueError — "gaul0_code" not found

# WRONG: expecting per-cell output
df = grid_to_country_month(...)
df.loc[(500, 12345)]  # 12345 is a pgid, not a country_id
```

---

## 10. Test Alignment

- **Green:** Correct aggregation with default country feature, correct MultiIndex shape
- **Beige:** Missing country feature raises ValueError, all-ocean grid produces empty DataFrame
- **Red:** Aggregation correctness: manual sum of known cells matches grouped output

Tests in `tests/test_grid_to_country_month.py` (if present).

---

## End of Contract

This document defines the **intended meaning** of `grid_to_country_month`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
