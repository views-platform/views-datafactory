# Class Intent Contract: ViewpointConfig

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-03-22
**Related ADRs:** ADR-009, ADR-014, ADR-016

---

## 1. Purpose

> Immutable configuration declaring which strategies and filters to apply when building a viewpoint from a consolidated event store.

Combines strategy selection (survivorship, distribution), event filtering (priogrid_gid, type_of_violence, where_prec), version tagging, and I/O paths into a single frozen config. Strategy names are validated against the strategy registries at config time.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** validate that `consolidated_path` exists (the file may not exist yet)
- This class does **not** perform any I/O, building, or transformation
- This class does **not** know about specific data sources (UCDP, ACLED, etc.)
- This class does **not** define strategies — it references them by name
- This class does **not** know about profiles — profiles create instances of this class

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Guarantees `version` is non-empty
- Guarantees `survivorship_strategy` is a registered strategy name
- Guarantees `distribution_strategy` is a registered strategy name
- All guarantees enforced via `__post_init__` validation

---

## 4. Inputs and Assumptions

- `consolidated_path`: Path, input consolidated event store (no default)
- `output_path`: Path, viewpoint output location (default: `data/viewpoints/ucdp_v1.parquet`)
- `ledger_path`: Path, provenance ledger (default: `provenance/viewpoint/ucdp_v1_ledger.jsonl`)
- `survivorship_strategy`: str, must be registered (default: `"annual_wins"`)
- `distribution_strategy`: str, must be registered (default: `"even_split"`)
- `min_priogrid_gid`: int | None, spatial filter threshold (default: None = no filter)
- `max_type_of_violence`: int | None, violence type filter (default: None = no filter)
- `exclude_where_prec`: tuple[int, ...], precision exclusion list (default: empty)
- `version`: str, non-empty provenance tag (default: `"custom"`)

Assumptions not met cause immediate `ValueError`.

---

## 5. Outputs and Side Effects

- No side effects. Pure configuration container.
- No derived properties or computed fields.

---

## 6. Failure Modes and Loudness

- `ValueError` on empty `version`
- `ValueError` on unregistered `survivorship_strategy`
- `ValueError` on unregistered `distribution_strategy`
- `AttributeError` on any attempt to mutate fields (frozen)

All failures are immediate and loud. No silent fallbacks.

---

## 7. Boundaries and Interactions

- Created directly or via `profiles.load_profile()`
- Consumed by viewpoint builders (e.g., `builders/ucdp_v1.py`)
- Strategy names resolved via `survivorship.get_survivorship()` and `temporal_distribution.get_distribution()`
- Must not depend on any other `datafactory_*` config class

---

## 8. Examples of Correct Usage

```python
cfg = ViewpointConfig(consolidated_path=Path("data/store.parquet"))
cfg = load_profile("production_parity", Path("data/store.parquet"))
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: unregistered strategy
ViewpointConfig(
    consolidated_path=p,
    survivorship_strategy="nonexistent",
)  # ValueError

# WRONG: empty version
ViewpointConfig(consolidated_path=p, version="")  # ValueError
```

---

## 10. Test Alignment

- **Green:** Default construction, custom parameters
- **Beige:** Invalid survivorship strategy, invalid distribution strategy, empty version
- **Red:** Mutation attempt (frozen enforcement)

Tests in `tests/test_viewpoint.py`.

---

## End of Contract

This document defines the **intended meaning** of `ViewpointConfig`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
