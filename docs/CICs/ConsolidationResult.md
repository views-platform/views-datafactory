# Class Intent Contract: ConsolidationResult

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-03-22
**Related ADRs:** ADR-008, ADR-013

---

## 1. Purpose

> Immutable result of a consolidation run, recording source counts, record counts, and content digest.

Provides a structured summary of what consolidation produced: how many sources were combined, how many records were new vs. already present, and the content digest of the output store.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** perform consolidation (that is the consolidator function)
- This class does **not** carry the consolidated data itself
- This class does **not** know about specific data sources
- This class does **not** carry per-source details (those are in the provenance ledger)

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Carries `output_path`: where the consolidated store was written
- Carries `n_sources`: number of source files processed
- Carries `n_records_total`: total records in the store after consolidation
- Carries `n_records_new`: records added in this run (0 if idempotent re-run)
- Carries `output_digest`: SHA-256 content digest of the output file

---

## 4. Inputs and Assumptions

- `output_path`: Path, location of the consolidated Parquet store
- `n_sources`: int, number of source files consolidated
- `n_records_total`: int, total records in the store
- `n_records_new`: int, newly added records
- `output_digest`: str, content digest of the output

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

- Created by consolidator functions (e.g., `consolidate_ucdp`)
- Consumed by orchestration scripts and provenance logging
- Must not depend on any `datafactory_*` class

---

## 8. Examples of Correct Usage

```python
result = consolidate_ucdp(config)
print(f"Added {result.n_records_new} new records, total {result.n_records_total}")
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: mutating the result
result.n_records_new = 0  # AttributeError (frozen)
```

---

## 10. Test Alignment

- **Green:** Correct counts after consolidation, digest non-empty
- **Beige:** Idempotent re-run produces n_records_new=0

Tests in `tests/test_consolidation.py`.

---

## End of Contract

This document defines the **intended meaning** of `ConsolidationResult`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
