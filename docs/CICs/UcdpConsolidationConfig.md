# Class Intent Contract: UcdpConsolidationConfig

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-05-03
**Related ADRs:** ADR-009, ADR-012, ADR-013, ADR-015, ADR-017

---

## 1. Purpose

> Immutable configuration for consolidating UCDP harvester snapshots into a single event store.

Carries source directories for all three UCDP harvester types (annual, candidate, .9), their harvest ledger paths, the consolidated store output path, and the consolidation ledger path. More complex than `AcledConsolidationConfig` because UCDP has three independent harvester sources that are consolidated together.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** validate that paths exist (directories are created at consolidation time)
- This class does **not** know about the harvester, viewpoints, or compilation
- This class does **not** contain event schema definitions (those are module-level constants)
- This class does **not** contain deduplication keys or survivorship strategies
- This class does **not** enforce that all three source dirs are populated

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Carries `annual_dir`: where to find raw UCDP annual Parquet snapshots
- Carries `candidate_dir`: where to find raw UCDP candidate Parquet snapshots
- Carries `dot9_dir`: where to find raw UCDP .9 Parquet snapshots
- Carries `annual_ledger_path`: annual harvest provenance for digest/timestamp lookup
- Carries `candidate_ledger_path`: candidate harvest provenance
- Carries `dot9_ledger_path`: .9 harvest provenance
- Carries `output_path`: consolidated store destination
- Carries `ledger_path`: consolidation provenance ledger destination

---

## 4. Inputs and Assumptions

- `annual_dir`: Path (default: `data/raw/ucdp_annual`)
- `candidate_dir`: Path (default: `data/raw/ucdp_candidate`)
- `dot9_dir`: Path (default: `data/raw/ucdp_dot9`)
- `annual_ledger_path`: Path (default: `provenance/ucdp_annual/ingestion_ledger.jsonl`)
- `candidate_ledger_path`: Path (default: `provenance/ucdp_candidate/ingestion_ledger.jsonl`)
- `dot9_ledger_path`: Path (default: `provenance/ucdp_dot9/ingestion_ledger.jsonl`)
- `output_path`: Path (default: `data/consolidated/ucdp_store.parquet`)
- `ledger_path`: Path (default: `provenance/consolidation/ucdp_ledger.jsonl`)

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

- Used by `consolidate_ucdp` as the sole configuration input
- Paths consumed by `read_store`, `write_store`, `append_ledger_entry`, and `_build_harvest_index`
- Must not depend on any other `datafactory_*` config class
- Registered via `register_consolidator("ucdp", ...)`

---

## 8. Examples of Correct Usage

```python
cfg = UcdpConsolidationConfig()  # Standard defaults
cfg = UcdpConsolidationConfig(
    annual_dir=Path("custom/raw/ucdp_annual"),
    output_path=Path("custom/store/ucdp.parquet"),
)
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: attempting to mutate
cfg = UcdpConsolidationConfig()
cfg.annual_dir = Path("other")  # AttributeError
```

---

## 10. Test Alignment

- **Green:** Default construction, custom paths
- **Beige:** Not applicable (config has no validation constraints; consolidator edge cases are in `TestConsolidateUcdpBeige`)
- **Red:** Mutation attempt (frozen enforcement)

Tests in `tests/test_consolidation.py`.

---

## End of Contract

This document defines the **intended meaning** of `UcdpConsolidationConfig`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
