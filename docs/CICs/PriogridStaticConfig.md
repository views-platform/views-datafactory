# Class Intent Contract: PriogridStaticConfig

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-03-22
**Related ADRs:** ADR-009, ADR-012

---

## 1. Purpose

> Immutable configuration for fetching PRIO-GRID static features from the PRIO-GRID 2.0 API.

Governs API access (URL, timeout), storage paths, and optional variable selection. Static variables are frozen datasets (terrain, resources, land cover from 2009-2015 vintages) covering 64,818 land cells.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** fetch data (that is `fetch_priogrid_static`)
- This class does **not** validate API availability
- This class does **not** validate path existence (directories may not exist yet)
- This class does **not** know about yearly/dynamic PRIO-GRID variables
- This class does **not** know about UCDP or other data sources

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Guarantees `timeout >= 1`
- Provides sensible defaults (PRIO-GRID API URL, standard paths)
- `variables` field: `None` means all static variables; tuple means subset

---

## 4. Inputs and Assumptions

- `api_url`: str, PRIO-GRID API base URL (default: `https://grid.prio.org/api`)
- `data_dir`: Path, output directory for Parquet snapshots (default: `data/priogrid_static`)
- `ledger_path`: Path, provenance ledger (default: `provenance/priogrid_static/ingestion_ledger.jsonl`)
- `timeout`: int, >= 1, HTTP request timeout in seconds (default: `60`)
- `variables`: tuple[str, ...] | None, subset of variables to fetch (default: `None` = all static)

Assumptions not met cause immediate `ValueError`.

---

## 5. Outputs and Side Effects

- No side effects. Pure configuration container.
- No derived properties.

---

## 6. Failure Modes and Loudness

- `ValueError` on `timeout < 1`
- `AttributeError` on any attempt to mutate fields (frozen)

All failures are immediate and loud. No silent fallbacks.

---

## 7. Boundaries and Interactions

- Used by `fetch_priogrid_static` as the sole configuration input
- Storage paths consumed by Parquet write and `append_ledger_entry`
- Must not depend on any other `datafactory_*` config class
- Registered in the source registry via `register_source("priogrid_static", ...)`

---

## 8. Examples of Correct Usage

```python
cfg = PriogridStaticConfig()  # All static variables
cfg = PriogridStaticConfig(variables=("landarea", "mountains_mean"))
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: timeout too low
PriogridStaticConfig(timeout=0)  # ValueError

# WRONG: mutation
cfg.timeout = 120  # AttributeError (frozen)
```

---

## 10. Test Alignment

- **Green:** Config defaults, config immutability, discovery filtering, fetch + Parquet + provenance, local-first skip, source registration, schema declaration
- **Beige:** Timeout < 1, timeout negative
- **Red:** Empty cells from API, missing required fields in cell data

Tests in `tests/test_priogrid_static.py`.

---

## End of Contract

This document defines the **intended meaning** of `PriogridStaticConfig`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
