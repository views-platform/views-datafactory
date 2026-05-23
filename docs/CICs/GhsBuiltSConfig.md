# Class Intent Contract: GhsBuiltSConfig

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-05-23
**Related ADRs:** ADR-009, ADR-012, ADR-030, ADR-034

---

## 1. Purpose

> Immutable configuration for downloading GHS-BUILT-S built-up surface grid GeoTIFFs from the EU Joint Research Centre.

Carries epoch selection, raster resolution/CRS/release identifiers, storage paths, and HTTP timeout. Constructs download URLs and expected filenames deterministically from these fields.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** perform any I/O or network access
- This class does **not** store or manage credentials (JRC is open access)
- This class does **not** validate that `data_dir` or `ledger_path` exist (directories are created at fetch time)
- This class does **not** know about consolidation, viewpoints, or compilation
- This class does **not** validate raster content or GeoTIFF metadata

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Guarantees all `epochs` are members of `KNOWN_EPOCHS` (1975..2030 in 5-year steps)
- Guarantees `epochs` is non-empty
- Guarantees `timeout >= 1`
- Constructs deterministic download URLs via `download_url(epoch)` from `release`, `crs`, `resolution`
- Constructs deterministic TIF filenames via `tif_filename(epoch)` matching JRC naming convention

---

## 4. Inputs and Assumptions

- `epochs`: tuple[int, ...], non-empty subset of `KNOWN_EPOCHS` (default: all 12 epochs)
- `resolution`: str, raster resolution code (default: `"30ss"`)
- `crs`: str, coordinate reference system code (default: `"4326"`)
- `release`: str, JRC release identifier (default: `"R2023A"`)
- `data_dir`: Path, output directory for extracted GeoTIFFs (default: `data/raw/ghsbuilts`)
- `ledger_path`: Path, provenance ledger location (default: `provenance/ghsbuilts/ingestion_ledger.jsonl`)
- `timeout`: int, >= 1, HTTP request timeout in seconds (default: `600`)

Assumptions not met cause immediate `ValueError`.

---

## 5. Outputs and Side Effects

- No side effects. Pure configuration container.
- `download_url(epoch)` returns a deterministic URL string.
- `tif_filename(epoch)` returns a deterministic filename string.

---

## 6. Failure Modes and Loudness

- `ValueError` on empty `epochs`
- `ValueError` on any epoch not in `KNOWN_EPOCHS`
- `ValueError` on `timeout < 1`
- `AttributeError` on any attempt to mutate fields (frozen)

Runtime failures from `fetch_ghsbuilts` (the primary consumer):
- `ValueError` on unexpected ZIP contents — expected TIF filename not found (ADR-011: fail loud, no silent fallback to wrong file). Ledger records the failure with reason.
- `requests.RequestException` on network failure (after retries). Ledger records the failure.
- `zipfile.BadZipFile` on corrupt download. Ledger records the failure.

All failures are immediate and loud. No silent fallbacks.

---

## 7. Boundaries and Interactions

- Used by `fetch_ghsbuilts` as the sole configuration input
- Storage paths consumed by `Path.write_bytes` and `append_ledger_entry`
- Must not depend on any other `datafactory_*` config class
- Registered in the source registry via `register_source("ghsbuilts", ...)`

---

## 8. Examples of Correct Usage

```python
cfg = GhsBuiltSConfig()  # All 12 epochs, default paths
cfg = GhsBuiltSConfig(epochs=(2020, 2025))
cfg = GhsBuiltSConfig(data_dir=Path("/data/ghsbuilts"), timeout=1200)
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: unknown epoch
GhsBuiltSConfig(epochs=(1999,))  # ValueError

# WRONG: empty epochs
GhsBuiltSConfig(epochs=())  # ValueError

# WRONG: zero timeout
GhsBuiltSConfig(timeout=0)  # ValueError

# WRONG: mutating frozen config
cfg = GhsBuiltSConfig()
cfg.timeout = 300  # AttributeError
```

---

## 10. Test Alignment

- **Green:** Default construction, frozen enforcement, custom epochs, URL construction, TIF filename construction
- **Beige:** Unknown epoch rejection, zero timeout, negative timeout, empty epochs rejection
- **Red:** Network failure records ledger, corrupt ZIP raises, unexpected ZIP contents raises ValueError and records ledger (ADR-011: no silent fallback to wrong file)

Tests in `tests/test_ghsbuilts_harvester.py`.

---

## End of Contract

This document defines the **intended meaning** of `GhsBuiltSConfig`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
