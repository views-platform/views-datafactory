# Class Intent Contract: PregriddedCompilationConfig

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-05-19
**Related ADRs:** ADR-003, ADR-009, ADR-012, ADR-024, ADR-029

---

## 1. Purpose

> Immutable compilation configuration for placing pre-gridded data onto the spatiotemporal grid.

Unlike `CompilationConfig` (which expects event records with lat/lon and performs spatial lookup + temporal aggregation), this config handles data already keyed by `(pgid, month_id)`. The viewpoint has already resolved spatial and temporal coordinates; the compiler performs mechanical placement only.

Features are declared as `PregriddedFeatureSpec` instances (frozen dataclass with `name` and `value_field`). No aggregation strategies, filters, or spatial lookups. The compiler never infers features from Parquet columns (ADR-003).

WET-before-DRY: this is intentionally a separate class from `CompilationConfig`, not a subclass or conditional mode. If a fourth source also arrives pre-gridded, we refactor then (C-164).

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** validate source file existence (deferred to compile time)
- This class does **not** read or parse the source Parquet
- This class does **not** perform lat/lon lookup (data is already pgid-keyed)
- This class does **not** perform aggregation (values are already per cell-month)
- This class does **not** define grid geometry (delegates to `GridConfig`)
- This class does **not** define temporal range (delegates to `TemporalConfig`)
- This class does **not** perform compilation (that is `compile_pregridded`)

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Guarantees features are non-empty (`__post_init__` validation)
- Guarantees feature names are unique (`__post_init__` validation)
- Guarantees `output_dtype` is in allowed set (`__post_init__` validation)
- Guarantees all field names are explicit -- `pgid_field` and `month_id_field` are declared in config, never hardcoded
- Grid output uses canonical `[T, H, W, C]` dimension order (ADR-024)
- Produces same output format as `compile_grid()`: grid.npy, pgids.npy, time_steps.npy, feature_names.json, provenance.json

---

## 4. Inputs and Assumptions

| Field | Type | Default | Validation |
|-------|------|---------|------------|
| `source_path` | `Path` | (required) | Not validated at config time |
| `grid_config` | `GridConfig` | `DEFAULT_GRID_CONFIG` | Delegated |
| `temporal_config` | `TemporalConfig` | `DEFAULT_TEMPORAL_CONFIG` | Delegated |
| `features` | `tuple[PregriddedFeatureSpec, ...]` | `()` | Non-empty, no duplicate names |
| `output_dir` | `Path` | `data/compiled` | None |
| `ledger_path` | `Path` | `provenance/compiler/...` | None |
| `pgid_field` | `str` | `"pgid"` | None |
| `month_id_field` | `str` | `"month_id"` | None |
| `output_dtype` | `str` | `"float32"` | Whitelist: float16/32/64, int32/64 |
| `fill_value` | `float` | `0.0` | None |

Empty `features` causes immediate `ValueError`. Duplicate feature names cause immediate `ValueError`.

---

## 5. Outputs and Side Effects

- No side effects. Pure configuration container.
- `PregriddedFeatureSpec(name, value_field)` is a frozen dataclass mapping output feature name to source Parquet column name.

---

## 6. Failure Modes and Loudness

- `ValueError` on empty `features` tuple
- `ValueError` on duplicate feature names
- `ValueError` on invalid `output_dtype` (not in allowed set)
- `AttributeError` on any attempt to mutate fields (frozen)
- Source file existence is NOT checked -- `FileNotFoundError` is raised by `compile_pregridded`

All failures are immediate and loud. No silent fallbacks.

---

## 7. Boundaries and Interactions

- Imported by `pregridded_compilation.py` (the compiler reads this config)
- Composes `GridConfig` and `TemporalConfig` (delegates spatial/temporal backbone)
- No aggregation strategies (unlike `CompilationConfig`)
- No spatial lookup (unlike `CompilationConfig`)
- Parallel to `CompilationConfig` -- both produce identical output format

---

## 8. Invariants

1. `len(features) >= 1` at construction
2. All feature names are unique
3. `output_dtype` is in `_ALLOWED_DTYPES`
4. Output grid shape is always `[T, H, W, C]` where `C = len(features)`
5. Output files: grid.npy + pgids.npy + time_steps.npy + feature_names.json + provenance.json

---

## 9. Open Questions

- Should `fill_value` be validated (e.g., reject NaN)? Currently no validation.
- Should `pgid_field` / `month_id_field` be validated against source schema at config time? Currently deferred to compile time.

---

## 10. Test Alignment

Tests in `tests/test_ghspop_compilation.py`:

- **Green:** config defaults, frozen, empty features rejected, duplicate names rejected, correct shape, population placement, feature_names.json, provenance, fill value, sidecar files, multiple features
- **Beige:** empty input -> zero grid, month_id outside range skipped, pgid outside range skipped
- **Red:** missing source, missing pgid column, missing value column
