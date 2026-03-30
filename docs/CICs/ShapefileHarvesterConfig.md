# Class Intent Contract: ShapefileHarvesterConfig

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-03-22
**Related ADRs:** ADR-009, ADR-012

---

## 1. Purpose

> Immutable configuration for downloading the PRIO-GRID reference shapefile.

The shapefile is grid reference geometry (not a data source). It's a one-time download used for parity validation. This config governs the download URL, storage path, provenance ledger, and retry policy.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** parse the shapefile (that is `PyShpReader`)
- This class does **not** validate the shapefile content
- This class does **not** register in the source registry (grid geometry, not a data source per ADR-012)
- This class does **not** perform any I/O

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Guarantees `timeout >= 1`
- Guarantees `max_retries >= 1`
- Provides sensible defaults (PRIO shapefile URL, standard paths)

---

## 4. Inputs and Assumptions

- `url`: str, shapefile ZIP URL (default: PRIO-GRID v2 shapefile)
- `data_dir`: Path, storage directory (default: `data/raw/priogrid`)
- `ledger_path`: Path, provenance ledger (default: `provenance/priogrid/ingestion_ledger.jsonl`)
- `timeout`: int, >= 1, HTTP timeout in seconds (default: 120)
- `max_retries`: int, >= 1, download retry attempts (default: 3)

---

## 5. Outputs and Side Effects

- No side effects. Pure configuration container.

---

## 6. Failure Modes and Loudness

- `ValueError` on `timeout < 1`
- `ValueError` on `max_retries < 1`
- `AttributeError` on mutation (frozen)

---

## 7. Boundaries and Interactions

- Used by `fetch_shapefile` as the sole configuration input
- NOT in the source registry (grid geometry, not a data source)
- Lives in `datafactory_priogrid`, not `datafactory_harvester`

---

## 8. Examples of Correct Usage

```python
cfg = ShapefileHarvesterConfig()  # defaults
fetch_shapefile(cfg)
```

---

## 9. Examples of Incorrect Usage

```python
ShapefileHarvesterConfig(timeout=0)  # ValueError
```

---

## 10. Test Alignment

- **Green:** Full download flow, unchanged content heartbeat, existing files skip
- **Beige:** Retry on transient failure
- **Red:** (via download function) All retries exhausted

Tests in `tests/test_grid.py`.

---

## End of Contract

This document defines the **intended meaning** of `ShapefileHarvesterConfig`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
