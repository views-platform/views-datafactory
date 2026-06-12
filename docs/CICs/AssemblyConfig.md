# Class Intent Contract: AssemblyConfig

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-06-11
**Related ADRs:** ADR-003, ADR-009, ADR-011, ADR-012, ADR-029, ADR-036, ADR-040

---

## 1. Purpose

> Immutable configuration for grid assembly: declares all input directories, output destination, admin boundary fields, dtype, and disk-space safety margin.

Assembly is the final stage of the data graph — it combines compiled UCDP, compiled ACLED (optional), compiled GHS-POP population (optional), compiled GHS-BUILT-S (optional), compiled V-Dem (optional), compiled SHDI (optional), static PRIO-GRID features, and GAUL admin boundaries into the canonical `grid.npy`. The config ensures all paths and parameters are declared upfront and validated before any I/O.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** perform assembly (that is `main()` in `assemble_grid.py`)
- This class does **not** validate that input directories exist (deferred to assembly time)
- This class does **not** know about feature names or counts (those come from the source registry)
- This class does **not** define grid geometry or temporal range (those come from the compiled data)
- This class does **not** handle provenance logging

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Guarantees `admin_numeric_fields` is non-empty
- Guarantees `admin_numeric_fields` contains no duplicates
- Guarantees `output_dtype` is one of `float16`, `float32`, `float64`
- Guarantees `disk_space_margin` is >= 1.0
- `acled_grid_dir` defaults to None — assembly works without ACLED for local development
- `ghspop_grid_dir` defaults to None — assembly works without GHS-POP for local development
- `ghsbuilts_grid_dir` defaults to None — assembly works without GHS-BUILT-S for local development
- `vdem_grid_dir` defaults to None — assembly works without V-Dem for local development
- `shdi_grid_dir` defaults to None — assembly works without SHDI for local development
- Assembly must contribute all cells from each compiled source grid to the assembled grid without cell loss (ADR-040, Invariant 1)

---

## 4. Inputs and Assumptions

- `ucdp_grid_dir`: Path to compiled UCDP grid directory (default: `data/compiled`)
- `acled_grid_dir`: Path to compiled ACLED grid directory, or None to skip ACLED
- `ghspop_grid_dir`: Path to compiled GHS-POP grid directory, or None to skip GHS-POP
- `ghsbuilts_grid_dir`: Path to compiled GHS-BUILT-S grid directory, or None to skip GHS-BUILT-S
- `vdem_grid_dir`: Path to compiled V-Dem grid directory, or None to skip V-Dem
- `shdi_grid_dir`: Path to compiled SHDI grid directory, or None to skip SHDI
- `static_dir`: Path to PRIO-GRID static features (default: `data/raw/priogrid_static`)
- `admin_dir`: Path to GAUL admin boundaries (default: `data/raw/gaul_admin`)
- `output_dir`: Path for assembled output (default: `data/assembled`)
- `admin_numeric_fields`: tuple of GAUL field names to include as grid channels
- `admin_fill_value`: float, fill value for cells outside any admin boundary (default: -1.0)
- `output_dtype`: str, numpy dtype for the output grid (validated against whitelist)
- `disk_space_margin`: float, multiplier for estimated grid size in disk-space check (must be >= 1.0)

Empty `admin_numeric_fields` causes immediate `ValueError`. Duplicate field names cause immediate `ValueError`. Invalid `output_dtype` causes immediate `ValueError`. `disk_space_margin < 1.0` causes immediate `ValueError`.

---

## 5. Outputs and Side Effects

- No side effects. Pure configuration container.
- Default values embed the standard VIEWS directory layout.

---

## 6. Failure Modes and Loudness

- `ValueError` on empty `admin_numeric_fields`
- `ValueError` on duplicate `admin_numeric_fields`
- `ValueError` on `output_dtype` not in `{float16, float32, float64}`
- `ValueError` on `disk_space_margin < 1.0`
- `AttributeError` on any attempt to mutate fields (frozen)

All failures are immediate and loud. No silent fallbacks.

---

## 7. Boundaries and Interactions

- Defined in `scripts/assemble_grid.py` (script-level, not a library)
- Used only by the `main()` function in the same file
- Argparse populates fields from CLI arguments; the dataclass validates
- `refresh_pipeline.sh` passes `--acled-grid data/compiled/acled --ghspop-grid data/compiled/ghspop --ghsbuilts-grid data/compiled/ghsbuilts --vdem-grid data/compiled/vdem --shdi-grid data/compiled/shdi` to assembly — if any directory doesn't exist, assembly fails loud
- Must not depend on any `datafactory_*` package (scripts are consumers, not library code)

---

## 8. Examples of Correct Usage

```python
from scripts.assemble_grid import AssemblyConfig

# Standard production config
cfg = AssemblyConfig(
    acled_grid_dir=Path("data/compiled/acled"),
    ghspop_grid_dir=Path("data/compiled/ghspop"),
    ghsbuilts_grid_dir=Path("data/compiled/ghsbuilts"),
    vdem_grid_dir=Path("data/compiled/vdem"),
    shdi_grid_dir=Path("data/compiled/shdi"),
)

# Local development without ACLED or GHS-POP
cfg = AssemblyConfig()  # optional dirs default to None

# Custom admin fields
cfg = AssemblyConfig(
    admin_numeric_fields=("gaul0_code", "gaul1_code"),
)
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: Empty admin fields — will raise ValueError
AssemblyConfig(admin_numeric_fields=())

# WRONG: Invalid dtype — will raise ValueError
AssemblyConfig(output_dtype="int32")

# WRONG: Margin below 1.0 — will raise ValueError
AssemblyConfig(disk_space_margin=0.5)

# WRONG: Inferring input dirs from filesystem
dirs = [d for d in Path("data/compiled").iterdir() if d.is_dir()]  # Violates ADR-003
```

---

## 10. Test Alignment

- **Green:** Default construction, frozen enforcement, acled_grid_dir defaults to None, ghspop_grid_dir defaults to None, accepts Path
- **Beige:** Empty admin fields rejection, duplicate admin fields rejection, invalid dtype rejection, margin below 1.0 rejection
- **Red:** (via integration tests) Assembly with nonexistent acled/ghspop dir fails loud; assembly without acled/ghspop backward-compatible; cell-count conservation (ADR-040)

Tests in `tests/test_assemble.py`.

---

## End of Contract

This document defines the **intended meaning** of `AssemblyConfig`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
