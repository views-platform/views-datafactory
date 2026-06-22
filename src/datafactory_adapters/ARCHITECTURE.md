# datafactory_adapters -- Architecture

## Purpose

Consumer-facing adapters that convert the datafactory's canonical output ([T, H, W, C] numpy arrays) into transport formats for downstream consumers. This module sits alongside the data graph (ADR-012), not inside it.

**Extractability note:** This module is designed to be moved to `views-pipeline-core` or a dedicated micro-service when the adapter pattern matures across the VIEWS platform. Dependencies are intentionally minimal (numpy, pandas, views-frames).

## Responsibility Boundary

**Owns:**
- Grid array → DataFrame conversion (dense or sparse, configurable month_id encoding)
- Grid array → FeatureFrame conversion
- FeatureFrame re-export from views-frames v1.0 (analogous to PredictionFrame and EvaluationFrame)
- month_id encoding logic (configurable epoch)

**Does NOT own:**
- Grid array production (datafactory_compilation)
- Data fetching or consolidation (datafactory_harvester, datafactory_consolidation)
- Land mask computation (datafactory_priogrid)
- Consumer-specific transformations (feature engineering, normalization)

## Dependency Rules

**May import:** numpy, pandas, views-frames
**Must never import:** Any `datafactory_*` package. This ensures clean extractability.

## Package Structure

```
datafactory_adapters/
    __init__.py              # Public API: FeatureFrame, grid_to_dataframe, grid_to_feature_frame
    ARCHITECTURE.md          # This file
    _validation.py           # Shared shape validation helpers
    feature_frame.py         # FeatureFrame re-export shim (views-frames v1.0)
    grid_from_feature_frame.py  # FeatureFrame → [T, H, W, F] grid reconstruction
    grid_to_country_month.py # [T, H, W, C] → country-month DataFrame
    grid_to_dataframe.py     # [T, H, W, C] → DataFrame and FeatureFrame conversion
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| FeatureFrame | Input-side transport object (re-exported from views-frames v1.0): values (N, D, S), SpatioTemporalIndex {time, unit, level}, feature_names. Analogous to PredictionFrame. |
| grid_to_dataframe | Converts [T, H, W, C] → pandas DataFrame with (month_id, priogrid_gid) MultiIndex. |
| grid_to_feature_frame | Converts [T, H, W, C] → FeatureFrame with dense land-cell time series. |
| month_id_epoch | Configurable base year for month_id encoding. 0 = raw, 1980 = VIEWS convention. |

## Invariants

- FeatureFrame validates shape, required identifiers (time, unit), and feature_name count
- DataFrame output is sorted by index (month_id, priogrid_gid)
- No datafactory_* imports — extractability is a hard constraint
