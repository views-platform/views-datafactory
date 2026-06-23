# Class Intent Contract: VdemViewpointConfig

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-05-26
**Related ADRs:** ADR-009, ADR-012, ADR-035

---

## 1. Purpose

> Immutable configuration for building a V-Dem viewpoint: reading harvest Parquet (country-year), applying the ISO3-to-pgid crosswalk from GAUL admin boundaries, expanding annual data to monthly resolution, and writing a viewpoint Parquet with (pgid, month_id, variable_columns).

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** perform any I/O or data transformation
- This class does **not** validate that source files exist (checked at build time)
- This class does **not** manage the crosswalk data or GAUL admin boundaries
- This class does **not** know about compilation, assembly, or consumers
- This class does **not** handle NaN propagation policy (that is the compilation layer's concern)

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Guarantees `version` is non-empty
- Guarantees `variables` is non-empty
- Guarantees `start_year >= VIEWS_EPOCH_YEAR` (1980)
- Guarantees `end_year >= start_year`
- Guarantees `temporal_interpolation` is a valid strategy (`"step"` or `"linear"`)

---

## 4. Inputs and Assumptions

- `source_path`: Path, harvest Parquet location (default: `data/raw/vdem/vdem_v16.parquet`)
- `crosswalk_path`: Path, GAUL ISO3-to-pgid crosswalk (default: `data/raw/gaul_admin/iso3_code.parquet`)
- `output_path`: Path, viewpoint output location (default: `data/viewpoint/vdem_v1.parquet`)
- `ledger_path`: Path, provenance ledger (default: `provenance/viewpoint/vdem_v1_ledger.jsonl`)
- `variables`: tuple[str, ...], V-Dem variable codes (default: 22 variables from `VDEM_VARIABLES`)
- `start_year`: int, >= `VIEWS_EPOCH_YEAR` (1980), start of temporal range (default: `1980`)
- `end_year`: int, >= `start_year`, end of temporal range (default: `2025`)
- `temporal_interpolation`: str, temporal expansion strategy from `VALID_TEMPORAL_INTERPOLATIONS` (default: `"step"`)
- `version`: str, viewpoint version identifier (default: `"vdem_v1"`)

Assumptions not met cause immediate `ValueError`.

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

Runtime failures from `build_vdem_v1` (the primary consumer):
- `FileNotFoundError` if `source_path` or `crosswalk_path` does not exist
- `KeyError` if harvest Parquet lacks expected columns
- All failures are logged and recorded in the provenance ledger

All failures are immediate and loud. No silent fallbacks.

---

## 7. Boundaries and Interactions

- Used by `build_vdem_v1` as the sole configuration input (required argument)
- Created directly or via `from_shortcuts(source_path=..., crosswalk_path=...)`
- `source_path` reads output from `fetch_vdem` (Layer 1 harvester)
- `crosswalk_path` reads output from `harvest_shapefile` (GAUL admin boundaries)
- Must not depend on any other `datafactory_*` config class
- Viewpoint output is consumed by `compile_pregridded` via `PregriddedCompilationConfig`

---

## 8. Examples of Correct Usage

```python
cfg = VdemViewpointConfig()  # All defaults
cfg = VdemViewpointConfig.from_shortcuts(source_path=Path("data/raw/vdem/vdem_v16.parquet"))
cfg = VdemViewpointConfig(end_year=2024)
cfg = VdemViewpointConfig(
    variables=("v2x_libdem", "v2x_polyarchy"),
    start_year=2000,
    end_year=2025,
)
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: start_year before VIEWS epoch
VdemViewpointConfig(start_year=1970)  # ValueError

# WRONG: end before start
VdemViewpointConfig(start_year=2020, end_year=2010)  # ValueError

# WRONG: empty variables
VdemViewpointConfig(variables=())  # ValueError

# WRONG: mutating frozen config
cfg = VdemViewpointConfig()
cfg.end_year = 2030  # AttributeError
```

---

## 10. Test Alignment

- **Green:** Default construction, frozen enforcement, custom temporal range, custom variables
- **Beige:** start_year before epoch rejection, end_year before start_year, empty version, empty variables
- **Red:** Missing source file at build time, missing crosswalk, malformed Parquet columns

Tests in `tests/test_vdem_viewpoint.py`.

---

## End of Contract

This document defines the **intended meaning** of `VdemViewpointConfig`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
