# Class Intent Contract: grid_to_country_month

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-06-24
**Related ADRs:** ADR-012, ADR-025, ADR-039, ADR-040, ADR-048

---

## 1. Purpose

> Aggregates the canonical [T, H, W, C] grid array to a country-month DataFrame by summing feature values per (month_id, country_id) pair.

This is the bridge between grid-native data (one row per cell per month) and country-level analysis (one row per country per month). Uses a country identifier feature (default: `gaul0_code` per ADR-025) as the grouping key.

---

## 2. Non-Goals (Explicit Exclusions)

- This module does **not** perform feature engineering or transformations beyond summation
- This module does **not** apply temporal alignment or padding
- This module does **not** validate that the grid contains meaningful data (non-zero) — however, `assert_cm_conservation` (called internally) rejects NaN in extensive feature columns as a pipeline bug indicator (C-291)
- This module does **not** know about specific country codes or their semantics
- This module does **not** handle weighted aggregation (area-weighted, population-weighted)

---

## 3. Responsibilities and Guarantees

- Guarantees that the output DataFrame has a `(month_id, country_id)` MultiIndex
- Guarantees that the country feature column is excluded from the output (it becomes the index)
- Guarantees that cells with country_id <= 0 are excluded from aggregation. This includes ocean cells and any land cells not overlapping a GAUL polygon. Since ADR-039 (area-majority assignment), the excluded set is substantially smaller — the exclusion guarantee is unchanged, only the input data improved.
- Guarantees that aggregation is summation (groupby sum) — no averaging, no counting
- Guarantees `ValueError` if the specified country feature is not in `feature_names`
- Guarantees count conservation for extensive features (ADR-040): `sum(country totals) + sum(excluded cell values) = sum(all grid cells)`. Excluded cells are quantified and logged, never silently dropped.
- Reuses `_flatten_grid()` from `datafactory_adapters._flatten` for the initial flattening step

---

## 4. Inputs and Assumptions

- `grid`: numpy array of shape [T, H, W, C] — the assembled grid
- `pgids`: numpy array of shape [H, W] — cell ID array
- `time_steps`: numpy array of shape [T] — datetime64[M] timestamps
- `feature_names`: list of C strings — column names matching the C dimension
- `country_feature`: str, must exist in `feature_names` (default: `"gaul0_code"`)
- `land_pgids`: optional set of land cell IDs for filtering
- `month_id_epoch`: int, base year for month_id encoding (default: 0)
- `feature_agg_types`: optional `dict[str, str]` mapping feature names to aggregation types (`"extensive"`, `"intensive"`, `"static"`). When provided, enables type-aware aggregation (ADR-048).

Assumptions not met cause immediate `ValueError`.

---

## 5. Outputs and Side Effects

- Returns a `pd.DataFrame` with `(month_id, country_id)` MultiIndex
- When `feature_agg_types` is provided: one column per extensive feature (static features excluded from output). When not provided: one column per feature except the country feature.
- All values are sums over grid cells belonging to each (month, country) group
- Emits `UserWarning` when excluded cells (country_id <= 0) have nonzero values in declared-extensive features (`feature_agg_types` membership per ADR-048; no name inference per ADR-003 — C-302 resolved 2026-07-15). When `feature_agg_types` is not provided the warning is skipped, matching the conservation no-op for such callers (C-301). The warning includes the count of excluded cell-months and how many carry events. Since ADR-039, the number of excluded cells with events is substantially reduced.
- When `feature_agg_types` is provided (ADR-048): raises `ValueError` if any intensive features are present — summation is not meaningful for indices (fail-loud per ADR-011). Callers must remove intensive features or use `output_format='dataframe'`.

---

## 6. Failure Modes and Loudness

- `ValueError` if `country_feature` is not in `feature_names`
- `ValueError` if intensive features are present when `feature_agg_types` is provided (ADR-048, ADR-011)
- `RuntimeError` if any extensive feature column contains NaN when `feature_agg_types` identifies them — this indicates a pipeline bug, not missing data (C-291). Raised by `assert_cm_conservation` before summation.
- Delegates to `_flatten_grid()` for shape mismatches

All failures are immediate and loud. No silent fallbacks.

---

## 7. Boundaries and Interactions

- Imports `_flatten_grid` from `datafactory_adapters._flatten` (same package). It moved
  there in #379 so the shared numpy primitive has a home of its own instead of squatting
  in the pandas module, and so the pandas tier can eventually be deleted as whole files
- Imports `assert_cm_conservation` from `datafactory_adapters._conservation` (same package) for count conservation checks (ADR-040)
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

- **Green:** Correct aggregation with default country feature, correct MultiIndex shape; intensive feature raises ValueError when `feature_agg_types` is provided (ADR-048); extensive-only features aggregate correctly; static features excluded from output
- **Beige:** Missing country feature raises ValueError, all-ocean grid produces empty DataFrame; without `feature_agg_types`, all features are summed (backward compat)
- **Red:** Aggregation correctness: manual sum of known cells matches grouped output; count conservation equation verified per ADR-040 (`grid_total = cm_total + excluded_total` for all extensive features); NaN in extensive features raises RuntimeError before summation; NaN in intensive features does not raise; float64 regression guard proves partition-sum precision at 500K cells

Tests in `tests/test_grid_to_country_month.py` (if present).

---

## End of Contract

This document defines the **intended meaning** of `grid_to_country_month`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
