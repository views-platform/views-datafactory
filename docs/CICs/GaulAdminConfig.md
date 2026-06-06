# Class Intent Contract: GaulAdminConfig

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-06-06
**Related ADRs:** ADR-009, ADR-012, ADR-025, ADR-040

---

## 1. Purpose

> Immutable configuration for harvesting GAUL 2024 administrative boundaries from FAO and joining them to PRIO-GRID centroids.

Governs shapefile download URLs, centroid shapefile path, storage paths, timeout, and optional variable selection. Downloads GAUL Level 1 and Level 2 shapefiles, performs a spatial join (pyshp + shapely STRtree) against 259,200 PRIO-GRID centroids, and stores per-variable Parquet files with columns `(gid, value)`.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** fetch or join data (that is `fetch_gaul_admin`)
- This class does **not** validate URL availability or network access
- This class does **not** validate path existence (directories may not exist yet)
- This class does **not** know about UCDP, viewpoints, or compilation
- This class does **not** define which admin variables exist (that is `ADMIN_VARIABLES`)

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Guarantees `timeout >= 1`
- Provides sensible defaults (FAO GCS URLs, standard paths)
- `variables` field: `None` means all 7 admin variables; tuple means subset
- GAUL codes (`gaul0_code`) serve as the authoritative country identity column (ADR-025)
- GAUL levels (L0, L1, L2) form a reconciliation family: hierarchical reconciliation is mandatory across levels (ADR-040, Invariant 2)

---

## 4. Inputs and Assumptions

- `gaul_l1_url`: str, GAUL Level 1 shapefile zip URL (default: FAO GCS)
- `gaul_l2_url`: str, GAUL Level 2 shapefile zip URL (default: FAO GCS)
- `centroid_shapefile`: Path, PRIO-GRID centroid shapefile (default: `data/raw/priogrid/shapefile/priogrid_centroid.shp`)
- `data_dir`: Path, output directory for Parquet files (default: `data/raw/gaul_admin`)
- `cache_dir`: Path, cache for downloaded shapefiles (default: `data/raw/gaul_admin/shapefiles`)
- `ledger_path`: Path, provenance ledger (default: `provenance/gaul_admin/ingestion_ledger.jsonl`)
- `timeout`: int, >= 1, HTTP request timeout in seconds (default: `300`)
- `variables`: tuple[str, ...] | None, subset of variables to produce (default: `None` = all)

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

- Used by `fetch_gaul_admin` as the sole configuration input
- Shapefile downloads cached in `cache_dir` (local-first: skip if already extracted)
- L2 shapefile is the primary join source; L1 is fallback for unmatched centroids
- Storage paths consumed by Parquet write and `append_ledger_entry`
- Must not depend on any other `datafactory_*` config class
- Registered in the source registry via `register_source("gaul_admin", ...)`

---

## 8. Examples of Correct Usage

```python
cfg = GaulAdminConfig()  # All 7 admin variables
cfg = GaulAdminConfig(variables=("gaul0_code", "gaul1_code"))
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: timeout too low
GaulAdminConfig(timeout=0)  # ValueError

# WRONG: mutation
cfg.timeout = 120  # AttributeError (frozen)
```

---

## 10. Test Alignment

- **Green:** Config defaults, config immutability, source registration
- **Beige:** Timeout < 1
- **Red:** Missing centroid shapefile, missing shapefile fields; GAUL hierarchy consistency (every L2 unit nests within exactly one L1, every L1 within exactly one L0) per ADR-040

Tests: not yet written (harvester is script-tested via `scripts/harvest_gaul.py`).

---

## End of Contract

This document defines the **intended meaning** of `GaulAdminConfig`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
