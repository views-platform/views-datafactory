# Class Intent Contract: ComparisonResult

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-03-22
**Related ADRs:** ADR-008, ADR-009

---

## 1. Purpose

> Structured result from comparing two event snapshots to detect revisions, additions, and removals.

Quantifies the difference between a new snapshot and the previous one: how many events were added, removed, or revised, the total revision magnitude, and which specific events changed. Source-agnostic — the identity field and comparison keys are injected by the caller.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** perform comparison (that is `compare_snapshots()`)
- This class does **not** decide what to do with revisions (caller decides)
- This class does **not** know about specific data sources
- This class does **not** enforce immutability (mutable dataclass)

---

## 3. Responsibilities and Guarantees

- Carries `has_previous`: whether a previous snapshot existed for comparison
- Carries `n_added`, `n_removed`, `n_revised`: revision counts
- Carries `total_revision_magnitude`: sum of absolute differences across revised events
- Carries `revised_events`: list of dicts describing each revised event
- Collects `warnings`: observations about the comparison

---

## 4. Inputs and Assumptions

- `has_previous`: bool, whether a previous snapshot was found
- `n_added`: int, events in new but not previous (default: 0)
- `n_removed`: int, events in previous but not new (default: 0)
- `n_revised`: int, events present in both with field differences (default: 0)
- `total_revision_magnitude`: float, cumulative absolute field differences (default: 0.0)
- `revised_events`: list[dict], per-event revision details (default: empty)
- `warnings`: list[str], comparison observations (default: empty)

No `__post_init__` validation — fields are populated by `compare_snapshots()`.

---

## 5. Outputs and Side Effects

- No side effects. Data container only.
- When `has_previous` is False, all counts are zero (no comparison possible).

---

## 6. Failure Modes and Loudness

- No constructor failures (mutable dataclass, no validation).
- The class itself does not raise. Large revision magnitudes are reported via `warnings`.

---

## 7. Boundaries and Interactions

- Created exclusively by `compare_snapshots()` in `event_validation.py`
- Consumed by source orchestrators to log revision dynamics
- Used to detect candidate mutability (ADR-017)
- Must not depend on any `datafactory_*` class

---

## 8. Examples of Correct Usage

```python
comparison = compare_snapshots(old_path, new_events, id_field="id", key_fields=("best",))
if comparison.n_revised > 0:
    logger.info("Revised %d events", comparison.n_revised)
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: using n_added without checking has_previous
comparison = compare_snapshots(events, nonexistent_path, ...)
print(comparison.n_added)  # Misleading: has_previous=False, n_added=0
```

---

## 10. Test Alignment

- **Green:** Added/removed/revised events correctly counted
- **Beige:** No previous snapshot (has_previous=False), empty event list
- **Red:** Malformed previous Parquet, mismatched schemas

Tests in `tests/test_ucdp_annual.py` (via `compare_snapshots`).

---

## End of Contract

This document defines the **intended meaning** of `ComparisonResult`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
