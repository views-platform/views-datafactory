# Class Intent Contract: CompilationConfig

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-03-22
**Related ADRs:** ADR-001, ADR-003, ADR-009, ADR-012

---

## 1. Purpose

> Immutable compilation configuration declaring the source file, grid/temporal backbone, features to compute, output location, and source Parquet column mappings.

Features are declared as `FeatureSpec` instances (frozen dataclass with `name`, `strategy`, and optional `filter` dict). The compiler never infers features from Parquet columns (ADR-003). Per-feature filters enable disaggregation (e.g., by violence type).

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
- Guarantees all field names are explicit — column mappings (`lat_field`, `lon_field`, `date_field`) are declared in config, never hardcoded in the compiler
- Guarantees grid and temporal configs use standard defaults when not overridden
- Provides default features: `FeatureSpec("event_count", "count")` and `FeatureSpec("fatalities", "sum_best")`
- Grid output uses canonical `[T, H, W, C]` dimension order (time, height, width, channels)

---

## 4. Inputs and Assumptions

- `source_path`: Path to a Parquet file. **Not validated at config time** — existence is checked by `compile_grid` at compile time.
- `grid_config`: GridConfig instance (defaults to standard PRIO-GRID)
- `temporal_config`: TemporalConfig instance (defaults to 1989-2024)
- `features`: Non-empty tuple of `FeatureSpec(name, strategy, filter={})` instances
- `output_dir`: Path for compiled npy output
- `ledger_path`: Path for provenance JSONL ledger
- `lat_field`, `lon_field`, `date_field`: Column names in the source Parquet

Empty `features` causes immediate `ValueError`.

---

## 5. Outputs and Side Effects

- No side effects. Pure configuration container.
- Default values embed domain knowledge (UCDP column names, standard feature set).

---

## 6. Failure Modes and Loudness

- `ValueError` on empty `features` tuple
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
        FeatureSpec("ged_ns_count", "count", {"type_of_violence": 1}),
        FeatureSpec("ged_ns_best", "sum_best", {"type_of_violence": 1}),
    ),
)
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: Empty features — will raise ValueError
CompilationConfig(source_path=path, features=())

# WRONG: Inferring features from Parquet columns
features = [(col, "count") for col in table.column_names]  # Violates ADR-003
```

---

## 10. Test Alignment

- **Green:** Default config values, frozen enforcement, correct feature defaults
- **Beige:** Empty features rejection, source path validated at compile time (not config time)
- **Red:** (via TestCompileGridRed) NaN coordinates, missing fields, empty Parquet, malformed dates

Tests in `tests/test_compiler.py`.

---

## End of Contract

This document defines the **intended meaning** of `CompilationConfig`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
