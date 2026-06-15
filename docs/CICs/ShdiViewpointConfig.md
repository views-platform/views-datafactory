# Class Intent Contract: ShdiViewpointConfig

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-06-12
**Related ADRs:** ADR-009, ADR-012, ADR-036, ADR-040, ADR-042

---

## 1. Purpose

> Immutable configuration for building an SHDI viewpoint: reading harvest Parquet (GDL region-year), applying the GDL-to-pgid crosswalk from the SHDI harvester's spatial join, expanding annual data to monthly resolution (step function), and writing a viewpoint Parquet with (pgid, month_id, shdi, healthindex, edindex, incindex).

SHDI is an intensive quantity (ADR-040). Sums across cells are meaningless. The invariants are value range [0, 1] and spatial completeness, not count conservation.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** perform any I/O or data transformation
- This class does **not** validate that source files exist (checked at build time)
- This class does **not** manage the GDL crosswalk or spatial join (produced by the SHDI harvester)
- This class does **not** know about compilation, assembly, or consumers
- This class does **not** enforce the [0, 1] value range (that is the build function's responsibility)
- This class does **not** handle NaN propagation policy — NaN is preserved as-is through compilation and assembly (ADR-042). Imputation is a consumer concern, not a factory concern

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Guarantees `version` is non-empty
- Guarantees `variables` is non-empty
- Guarantees `start_year >= VIEWS_EPOCH_YEAR` (1980)
- Guarantees `end_year >= start_year`
- Guarantees `temporal_interpolation` is a valid strategy (`"step"` or `"linear"`)

Build function guarantees (enforced by `build_shdi_v1`, not the config):
- All output values for `shdi`, `healthindex`, `edindex`, `incindex` are in [0, 1] or NaN
- Output has exactly 12 monthly rows per (GDL region, year) per mapped pgid (step function — constant within year)
- Unmapped cells (no GDL region) are absent from the output (filled with NaN at compilation). NaN is never filled, interpolated, or imputed — see ADR-042 for rationale (MNAR missingness mechanism)
- Unmapped GDL codes produce a warning, not a crash

---

## 4. Inputs and Assumptions

- `source_path`: Path, harvest Parquet location (default: `data/raw/shdi/shdi_v10.2.parquet`)
- `crosswalk_path`: Path, GDL-to-pgid crosswalk (default: `data/raw/shdi/gdl_to_pgid.parquet`)
- `output_path`: Path, viewpoint output location (default: `data/viewpoint/shdi_v1.parquet`)
- `ledger_path`: Path, provenance ledger (default: `provenance/viewpoint/shdi_v1_ledger.jsonl`)
- `variables`: tuple[str, ...], SHDI indicator names (default: `("shdi", "healthindex", "edindex", "incindex")`)
- `start_year`: int, >= `VIEWS_EPOCH_YEAR` (1980), start of temporal range (default: `1990`)
- `end_year`: int, >= `start_year`, end of temporal range (default: `2023`)
- `temporal_interpolation`: str, temporal expansion strategy from `VALID_TEMPORAL_INTERPOLATIONS` (default: `"step"`)
- `version`: str, viewpoint version identifier (default: `"shdi_v1"`)

Assumptions not met cause immediate `ValueError`.

Source Parquet columns: `GDLCODE` (string), `Year` (int), plus one column per variable.
Crosswalk Parquet columns: `gid` (int32, pgid), `gdl_code` (string).

---

## 5. Outputs and Side Effects

- No side effects. Pure configuration container.
- All fields are accessible as frozen dataclass attributes.

---

## 6. Failure Modes and Loudness

- `ValueError` on empty `version`
- `ValueError` on empty `variables`
- `ValueError` on `start_year < VIEWS_EPOCH_YEAR`
- `ValueError` on `end_year < start_year`
- `ValueError` on `temporal_interpolation` not in `VALID_TEMPORAL_INTERPOLATIONS`
- `AttributeError` on any attempt to mutate fields (frozen)

Runtime failures from `build_shdi_v1` (the primary consumer):
- `FileNotFoundError` if `source_path` or `crosswalk_path` does not exist
- `KeyError` if harvest Parquet lacks expected columns (`GDLCODE`, `Year`, or any variable)
- Unmapped GDL codes (present in source but absent from crosswalk): warning logged, rows skipped, not a crash
- All failures are logged and recorded in the provenance ledger

All failures are immediate and loud. No silent fallbacks.

---

## 7. Boundaries and Interactions

- Used by `build_shdi_v1` as the sole configuration input (required argument)
- `source_path` reads output from `fetch_shdi` (Layer 1 harvester)
- `crosswalk_path` reads output from `fetch_shdi` (GDL spatial join, produced alongside harvest data)
- Must not depend on any other `datafactory_*` config class
- Viewpoint output is consumed by `compile_pregridded` via `PregriddedCompilationConfig`
- SHDI skips consolidation (single periodic release, ADR-036)

---

## 8. Examples of Correct Usage

```python
cfg = ShdiViewpointConfig()  # All defaults
cfg = ShdiViewpointConfig(end_year=2022)
cfg = ShdiViewpointConfig(
    variables=("shdi", "healthindex"),
    start_year=2000,
    end_year=2023,
)
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: start_year before VIEWS epoch
ShdiViewpointConfig(start_year=1970)  # ValueError

# WRONG: end before start
ShdiViewpointConfig(start_year=2020, end_year=2010)  # ValueError

# WRONG: empty variables
ShdiViewpointConfig(variables=())  # ValueError

# WRONG: mutating frozen config
cfg = ShdiViewpointConfig()
cfg.end_year = 2030  # AttributeError
```

---

## 10. Test Alignment

- **Green:** Default construction, frozen enforcement, basic expansion (correct row count, 12 months per year per pgid), output columns, values constant within year, month_id calculation (Jan 1990 → month_id 121), provenance ledger written, no duplicate (pgid, month_id) pairs, builder registry
- **Beige:** Unmapped GDL code warns (not crashes), year outside range filtered, crosswalk region not in source data, single year produces 12 rows
- **Red:** Missing source file, missing crosswalk file, empty version, empty variables, start_year before epoch, end_year before start_year

Tests in `tests/test_shdi_viewpoint.py`.

---

## End of Contract

This document defines the **intended meaning** of `ShdiViewpointConfig`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
