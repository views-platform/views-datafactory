# Class Intent Contract: SourceEntry

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-05-07
**Related ADRs:** ADR-003, ADR-009, ADR-011, ADR-018

---

## 1. Purpose

> Immutable declaration of a pipeline data source: its identity, required credentials, contributed features, freshness SLO, provenance ledger path, and compiled output directory.

The source registry (`PIPELINE_SOURCES`) is a tuple of `SourceEntry` instances that serves as the single source of truth for pipeline infrastructure. Health checks, pre-flight validation, assembly, and remote verification all import from the registry instead of maintaining hardcoded lists. Adding or removing a source is a one-entry change.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** harvest data or call external APIs
- This class does **not** read or write files
- This class does **not** validate file existence (pre-flight checks do that separately)
- This class does **not** define aggregation strategies or compilation logic
- This class does **not** know about grid geometry or temporal range

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Guarantees `name` is non-empty (`__post_init__` validation)
- Guarantees `required_env_vars` contains no empty strings
- Guarantees `features` contains no empty strings
- Guarantees `slo_hours` is positive when set (None means static/never-stale)
- Feature ordering within `PIPELINE_SOURCES` defines the canonical feature order in the assembled grid

---

## 4. Inputs and Assumptions

- `name`: str, human-readable source identifier. Must be unique across the registry.
- `required_env_vars`: tuple of environment variable names needed by this source's harvester. Empty for sources without credentials (e.g., PRIO-GRID).
- `features`: tuple of feature names this source contributes to the assembled grid. Empty for sources that don't produce grid features directly (e.g., downstream layers like Consolidation).
- `slo_hours`: maximum acceptable age in hours. None for static sources.
- `ledger_path`: Path relative to the provenance root. Health scripts prepend their `--provenance-dir` argument.
- `compiled_dir`: Path to compiled output directory. Used by pre-flight to verify compilation products exist.

Empty `name` causes immediate `ValueError`. Empty strings in `required_env_vars` or `features` cause immediate `ValueError`. Non-positive `slo_hours` causes immediate `ValueError`.

---

## 5. Outputs and Side Effects

- No side effects. Pure configuration container.
- Default values are empty tuples and None — a minimal `SourceEntry` needs only a name.

---

## 6. Failure Modes and Loudness

- `ValueError` on empty `name`
- `ValueError` on empty string in `required_env_vars`
- `ValueError` on empty string in `features`
- `ValueError` on `slo_hours <= 0`
- `AttributeError` on any attempt to mutate fields (frozen)

All failures are immediate and loud. No silent fallbacks.

---

## 7. Boundaries and Interactions

- Lives in `datafactory_provenance.source_registry` (Layer 0)
- Imported by: `scripts/preflight.py`, `scripts/check_health.py`, `scripts/verify_remote.py`, `scripts/assemble_grid.py`
- `PIPELINE_SOURCES` is the canonical tuple; helper functions `get_source_slo()`, `get_all_features()`, `get_required_env_vars()`, and `validate_preflight()` derive views from it
- Must not depend on any `datafactory_*` package other than provenance (Layer 0 constraint)

---

## 8. Examples of Correct Usage

```python
from datafactory_provenance.source_registry import (
    PIPELINE_SOURCES, SourceEntry, get_all_features, validate_preflight,
)

# Registry-driven feature list
features = get_all_features()  # 51 features in canonical order

# Pre-flight credential check
results = validate_preflight()
for r in results:
    print(f"{r['name']} ({r['source']}): {r['status']}")

# Custom source for testing
test_source = SourceEntry(
    name="Test Source",
    required_env_vars=("TEST_TOKEN",),
    features=("test_count",),
    slo_hours=24,
)
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: Empty name — will raise ValueError
SourceEntry(name="")

# WRONG: Inferring sources from the filesystem (violates ADR-003)
sources = [SourceEntry(name=d.name) for d in Path("data/raw").iterdir()]

# WRONG: Duplicating source metadata outside the registry
SOURCE_SLO = {"UCDP Annual": 8760, ...}  # Use get_source_slo() instead
```

---

## 10. Test Alignment

- **Green:** Valid construction, frozen enforcement, None slo allowed, feature count is 51, canonical feature order (UCDP first, admin last)
- **Beige:** Empty name/var/feature rejection, non-positive slo rejection, no duplicate names or features in registry
- **Red:** `validate_preflight` with missing/empty env vars produces FAIL results

Tests in `tests/test_source_registry.py`.

---

## End of Contract

This document defines the **intended meaning** of `SourceEntry`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
