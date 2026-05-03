# Class Intent Contract: AcledConsolidationConfig

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-05-02
**Related ADRs:** ADR-009, ADR-012, ADR-013

---

## 1. Purpose

> Immutable configuration for consolidating ACLED harvester snapshots into a single event store.

Carries source directory, harvest ledger path, output path, and consolidation ledger path. No validation beyond immutability — all four fields are Paths with sensible defaults.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** validate that paths exist (directories are created at consolidation time)
- This class does **not** know about the harvester, viewpoints, or compilation
- This class does **not** contain event schema definitions (those are module-level constants)
- This class does **not** contain deduplication keys or strategies

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Carries `source_dir`: where to find raw ACLED Parquet snapshots
- Carries `harvest_ledger_path`: harvest provenance for digest/timestamp lookup
- Carries `output_path`: consolidated store destination
- Carries `ledger_path`: consolidation provenance ledger destination

---

## 4. Inputs and Assumptions

- `source_dir`: Path (default: `data/raw/acled`)
- `harvest_ledger_path`: Path (default: `provenance/acled/ingestion_ledger.jsonl`)
- `output_path`: Path (default: `data/consolidated/acled/acled_store.parquet`)
- `ledger_path`: Path (default: `provenance/consolidation/acled_ledger.jsonl`)

No validation constraints beyond frozen immutability.

---

## 5. Outputs and Side Effects

- No side effects. Pure configuration container.
- No derived properties or computed fields.

---

## 6. Failure Modes and Loudness

- `AttributeError` on any attempt to mutate fields (frozen)
- No constructor validation failures (all fields have defaults, no constraints)

---

## 7. Boundaries and Interactions

- Used by `consolidate_acled` as the sole configuration input
- Paths consumed by `read_store`, `write_store`, `append_ledger_entry`, and `_build_harvest_index`
- Must not depend on any other `datafactory_*` config class
- Registered via `register_consolidator("acled", ...)`

---

## 8. Examples of Correct Usage

```python
cfg = AcledConsolidationConfig()  # Standard defaults
cfg = AcledConsolidationConfig(
    source_dir=Path("custom/raw/acled"),
    output_path=Path("custom/store/acled.parquet"),
)
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: attempting to mutate
cfg = AcledConsolidationConfig()
cfg.source_dir = Path("other")  # AttributeError
```

---

## 10. Test Alignment

- **Green:** Default construction, custom paths
- **Beige:** Not applicable (config has no validation constraints; consolidator edge cases are in `TestConsolidateAcledBeige`)
- **Red:** Mutation attempt (frozen enforcement)

Tests in `tests/test_acled_consolidation.py`.

---

## End of Contract

This document defines the **intended meaning** of `AcledConsolidationConfig`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
