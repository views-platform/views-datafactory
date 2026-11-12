# Class Intent Contract: CompilationConfig

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-06-06
**Related ADRs:** ADR-001, ADR-003, ADR-009, ADR-012, ADR-024, ADR-040

---

## 1. Purpose

> Immutable compilation configuration declaring the source file, grid/temporal backbone, features to compute, output location, and source Parquet column mappings.

Features are declared as `FeatureSpec` instances (frozen dataclass with `name`, `strategy`, optional `filter` dict, and `value_field`). The compiler never infers features from Parquet columns (ADR-003). Per-feature filters enable disaggregation (e.g., by violence type). The `value_field` parameter controls which event field is aggregated (default: `"best"`).

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** validate source file existence (deferred to compile time — the file may not exist yet at config construction)
- This class does **not** read or parse the source Parquet
- This class does **not** define aggregation strategies (those live in `aggregation.py`)
- This class does **not** define grid geometry (delegates to `GridConfig`)
- This class does **not** define temporal range (delegates to `TemporalConfig`)
- This class does **not** perform compilation (that is `compile_grid`)

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Guarantees features are non-empty (`__post_init__` validation)
- Guarantees feature names are unique (`__post_init__` validation)
- Guarantees all field names are explicit — column mappings (`lat_field`, `lon_field`, `date_field`, `pgid_field`) are declared in config, never hardcoded in the compiler
- Guarantees a **declared cell beats a derived one**: when `pgid_field` is set, a row's value in that column determines its grid cell, and `lat_field`/`lon_field` are consulted only for rows where the declared value is null or outside `[1, n_cells]` (ADR-015, ADR-003). Rows whose declared value is unusable are counted separately from rows that carry none, and any unusable value is reported — a fallback for decision-relevant placement may not be silent
- Guarantees grid and temporal configs use standard defaults when not overridden
- Provides default features: `FeatureSpec("event_count", "count")` and `FeatureSpec("fatalities", "sum_field")`
- Grid output uses canonical `[T, H, W, C]` dimension order (time, height, width, channels)
- The compiler (`compile_grid`) enforces count conservation (ADR-040) for all features compiled from this config: `placed + skipped_spatial + skipped_temporal = input_rows`

---

## 4. Inputs and Assumptions

- `source_path`: Path to a Parquet file. **Not validated at config time** — existence is checked by `compile_grid` at compile time.
- `grid_config`: GridConfig instance (defaults to standard PRIO-GRID)
- `temporal_config`: TemporalConfig instance (defaults to 1989-2024)
- `features`: Non-empty tuple of `FeatureSpec(name, strategy, filter={}, value_field="best")` instances
- `output_dir`: Path for compiled npy output
- `ledger_path`: Path for provenance JSONL ledger
- `lat_field`, `lon_field`, `date_field`: Column names in the source Parquet
- `pgid_field`: Column name holding a grid cell an upstream stage has already decided, or `None`. **Default `None`**, which places purely by coordinates — the behaviour every caller had before this field existed. Set it only for a source whose cells were decided upstream; for a source nobody relocates (ACLED events are single-day points), the coordinates *are* the authority and this stays unset. Its pregridded counterpart is `PregriddedCompilationConfig.pgid_field`.
- `output_dtype`: str, numpy dtype for output grid (default: `"float32"`, validated against whitelist)
- `fill_value`: float, fill value for empty (cell, month) bins (default: `0.0`)

Empty `features` causes immediate `ValueError`. Duplicate feature names cause immediate `ValueError`.

A `pgid_field` naming a column the source does not contain is **not** detected at config
time. `compile_grid` fails at compile time with the missing column named, which is loud
but late; a caller passing an unverified field name should expect the failure there.

---

## 5. Outputs and Side Effects

- No side effects. Pure configuration container.
- Default values embed domain knowledge (UCDP column names, standard feature set).

---

## 6. Failure Modes and Loudness

- `ValueError` on empty `features` tuple
- `ValueError` on duplicate feature names
- `ValueError` on invalid `output_dtype` (not in allowed set)
- `AttributeError` on any attempt to mutate fields (frozen)
- Source file existence is NOT checked — `FileNotFoundError` is raised later by `compile_grid`

All failures are immediate and loud. No silent fallbacks.

---

## 7. Boundaries and Interactions

- Imported by `grid_compilation.py` (the compiler reads this config)
- Composes `GridConfig` and `TemporalConfig` (delegates spatial/temporal backbone)
- References aggregation strategies by name (string), not by import (loose coupling)
- The compiler uses `compute_file_digest` to hash both source Parquet and output grid npy (chunked, memory-safe)
- Must not depend on harvester, consolidation, or viewpoint packages (ADR-012)

---

## 8. Examples of Correct Usage

```python
from datafactory_compilation import CompilationConfig, compile_grid

# Standard compilation with all defaults
cfg = CompilationConfig(source_path=Path("data/viewpoint/ucdp_v1.parquet"))
compile_grid(cfg)

# Custom features and column mapping
cfg = CompilationConfig(
    source_path=Path("data/acled.parquet"),
    features=(FeatureSpec("event_count", "count"),),
    lat_field="lat",
    lon_field="lon",
    date_field="event_date",
)

# Disaggregated by violence type
from datafactory_compilation import FeatureSpec
cfg = CompilationConfig(
    source_path=path,
    features=(
        FeatureSpec("ged_sb_count", "count", {"type_of_violence": 1}),
        FeatureSpec("ged_sb_best", "sum_field", {"type_of_violence": 1}),
    ),
)
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: Empty features — will raise ValueError
CompilationConfig(source_path=path, features=())

# WRONG: Duplicate feature names — will raise ValueError
CompilationConfig(source_path=path, features=(
    FeatureSpec("event_count", "count"),
    FeatureSpec("event_count", "sum_field"),  # duplicate name
))

# WRONG: Inferring features from Parquet columns
features = [(col, "count") for col in table.column_names]  # Violates ADR-003
```

---

## 10. Test Alignment

- **Green:** Default config values, frozen enforcement, correct feature defaults
- **Beige:** Empty features rejection, source path validated at compile time (not config time)
- **Red:** (via TestCompileGridRed) NaN coordinates, missing fields, empty Parquet, malformed dates; placement conservation assertion (ADR-040)

Tests in `tests/test_compiler.py`.

---

## End of Contract

This document defines the **intended meaning** of `CompilationConfig`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
