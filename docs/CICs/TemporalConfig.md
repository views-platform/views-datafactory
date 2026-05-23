# Class Intent Contract: TemporalConfig

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-05-23
**Related ADRs:** ADR-001, ADR-009

---

## 1. Purpose

> Immutable temporal backbone configuration defining the year/month range for a spatiotemporal grid.

Default values produce the standard VIEWS temporal range: January 1989 to December 2026 (456 monthly steps).

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** generate time step arrays (that is `generate_time_steps`)
- This class does **not** know about spatial coordinates
- This class does **not** define the VIEWS month_id convention (that is `to_views_month_id` / `from_views_month_id`)
- This class does **not** store data values

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Guarantees all temporal parameters are valid after construction (`__post_init__` validation)
- Guarantees years are >= 1
- Guarantees months are in [1, 12]
- Guarantees start is not after end
- Provides derived values as properties: `start_dt`, `end_dt` (numpy datetime64[M]), `n_steps`

---

## 4. Inputs and Assumptions

- `start_year`, `end_year`: int, >= 1
- `start_month`, `end_month`: int, in [1, 12]
- Start must not be after end (validated via month ordinals: `year * 12 + month`)

Note: The ordinal comparison is for validation only. It is NOT the VIEWS month_id convention (which uses a 1980 epoch). See `temporal_generator.py` for VIEWS month_id conversion.

Assumptions not met cause immediate `ValueError`.

---

## 5. Outputs and Side Effects

- No side effects. Pure configuration container.
- `start_dt`, `end_dt`: numpy datetime64[M] representations
- `n_steps`: total monthly steps (inclusive), computed as `(end_year - start_year) * 12 + (end_month - start_month) + 1`

---

## 6. Failure Modes and Loudness

- `ValueError` on year < 1
- `ValueError` on month outside [1, 12]
- `ValueError` on start after end
- `AttributeError` on mutation attempt (frozen)

All failures are immediate and loud. No silent fallbacks.

---

## 7. Boundaries and Interactions

- Composed into `SpatioTemporalGrid` as a peer alongside `GridConfig`
- Used by `generate_time_steps` to produce datetime64[M] arrays
- Must not depend on spatial grid configuration

---

## 8. Examples of Correct Usage

```python
cfg = TemporalConfig()  # 1989-01 to 2026-12: 456 steps
cfg = TemporalConfig(start_year=2000, end_year=2020)  # Custom range
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: end before start
TemporalConfig(start_year=2025, end_year=2024)  # ValueError

# WRONG: inferring temporal range from array length
n_months = data.shape[1]  # Violates ADR-003
```

---

## 10. Test Alignment

- **Green:** Default step count (456), derived datetime properties
- **Beige:** Start after end, month outside range, negative year
- **Red:** Mutation attempt (frozen enforcement)

Tests in `tests/test_grid.py` (via spec tests) and `tests/test_provenance.py` (indirectly).

---

## End of Contract

This document defines the **intended meaning** of `TemporalConfig`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
