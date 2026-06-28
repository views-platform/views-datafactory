# Class Intent Contract: ViewpointResult

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-06-28
**Related ADRs:** ADR-008, ADR-014, ADR-049

---

## 1. Purpose

> Immutable result of a viewpoint build, recording event counts, summary expansion, filtering, and content digest.

Provides a structured summary of what the viewpoint builder produced: how many events went in, how many came out (after survivorship, expansion, and filtering), and the content digest of the output.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** perform viewpoint building (that is the builder function)
- This class does **not** carry the viewpoint data itself
- This class does **not** know about specific strategies or filters

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Carries `output_path`: where the viewpoint Parquet was written
- Carries `n_events_input`: events in the consolidated store
- Carries `n_events_output`: rows in the viewpoint output (may differ due to survivorship dedup and summary event expansion)
- Carries `n_summary_expanded`: summary events that were expanded across months
- Carries `n_spatially_distributed`: events that were spatially distributed across polygon cells (ADR-049)
- Carries `n_filtered`: events removed by filters
- Carries `output_digest`: SHA-256 content digest of the output file
- Carries `version`: viewpoint version tag from config

---

## 4. Inputs and Assumptions

- `output_path`: Path, location of the viewpoint Parquet
- `n_events_input`: int, input event count
- `n_events_output`: int, output row count
- `n_summary_expanded`: int, summary events expanded
- `n_spatially_distributed`: int, events spatially distributed across polygon cells
- `n_filtered`: int, events removed by filters
- `output_digest`: str, content digest of the output
- `version`: str, version tag

All fields are required. No defaults.

---

## 5. Outputs and Side Effects

- No side effects. Pure result container.
- No derived properties.

---

## 6. Failure Modes and Loudness

- `AttributeError` on any attempt to mutate fields (frozen)
- No constructor validation failures.

---

## 7. Boundaries and Interactions

- Created by viewpoint builder functions (e.g., `build_ucdp_v1`)
- Consumed by orchestration scripts and provenance logging
- Must not depend on any `datafactory_*` class

---

## 8. Examples of Correct Usage

```python
result = build_ucdp_v1(config)
print(f"Input: {result.n_events_input}, Output: {result.n_events_output}")
print(f"Expanded {result.n_summary_expanded} summary, distributed {result.n_spatially_distributed} spatial, filtered {result.n_filtered}")
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: mutating the result
result.version = "v2"  # AttributeError (frozen)
```

---

## 10. Test Alignment

- **Green:** Correct counts after build, digest non-empty, version matches config
- **Beige:** No events after filtering (n_events_output=0)

Tests in `tests/test_viewpoint.py`.

---

## End of Contract

This document defines the **intended meaning** of `ViewpointResult`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
