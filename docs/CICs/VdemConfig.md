# Class Intent Contract: VdemConfig

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-05-26
**Related ADRs:** ADR-009, ADR-012, ADR-035

---

## 1. Purpose

> Immutable configuration for downloading V-Dem (Varieties of Democracy) country-year data from the V-Dem Institute.

Carries download URL, declared variable list, storage paths, version identifier, and HTTP timeout. Constructs the output Parquet path deterministically from version.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** perform any I/O or network access
- This class does **not** parse or filter CSV data (that is `_parse_and_filter`)
- This class does **not** know about crosswalks, viewpoints, or compilation
- This class does **not** validate that `data_dir` or `ledger_path` exist (directories are created at fetch time)
- This class does **not** manage the country-to-grid mapping

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Guarantees `variables` is non-empty with no duplicates and no empty strings
- Guarantees `timeout >= 1`
- Guarantees `version` is non-empty
- Constructs deterministic output path via `output_path` property: `data_dir / f"vdem_{version}.parquet"`

---

## 4. Inputs and Assumptions

- `download_url`: str, V-Dem distribution URL (default: `DEFAULT_DOWNLOAD_URL`)
- `variables`: tuple[str, ...], V-Dem variable codes to extract (default: 22 variables from `VDEM_VARIABLES`)
- `data_dir`: Path, output directory for filtered Parquet (default: `data/raw/vdem`)
- `ledger_path`: Path, provenance ledger location (default: `provenance/vdem/ingestion_ledger.jsonl`)
- `version`: str, V-Dem release identifier (default: `"v16"`)
- `timeout`: int, >= 1, HTTP request timeout in seconds (default: `300`)

Assumptions not met cause immediate `ValueError`.

---

## 5. Outputs and Side Effects

- No side effects. Pure configuration container.
- `output_path` property returns `data_dir / f"vdem_{version}.parquet"`.

---

## 6. Failure Modes and Loudness

- `ValueError` on empty `variables`
- `ValueError` on duplicate variable name
- `ValueError` on empty string in `variables`
- `ValueError` on `timeout < 1`
- `ValueError` on empty `version`
- `AttributeError` on any attempt to mutate fields (frozen)

Runtime failures from `fetch_vdem` (the primary consumer):
- `requests.RequestException` on network failure (after retries). Ledger records the failure.
- `zipfile.BadZipFile` on corrupt download. Ledger records the failure.
- `ValueError` on CSV missing expected columns (via `_parse_and_filter`). Ledger records the failure with the specific column error before re-raising (C-207).

All failures are immediate and loud. No silent fallbacks.

---

## 7. Boundaries and Interactions

- Used by `fetch_vdem` as the sole configuration input
- Storage paths consumed by `Path.write_bytes` and `append_ledger_entry`
- Must not depend on any other `datafactory_*` config class
- Registered in the source registry via `PIPELINE_SOURCES`

---

## 8. Examples of Correct Usage

```python
cfg = VdemConfig()  # All 22 variables, default paths
cfg = VdemConfig(variables=("v2x_libdem", "v2x_polyarchy"))
cfg = VdemConfig(version="v17", timeout=600)
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: empty variables
VdemConfig(variables=())  # ValueError

# WRONG: duplicate variable
VdemConfig(variables=("v2x_libdem", "v2x_libdem"))  # ValueError

# WRONG: zero timeout
VdemConfig(timeout=0)  # ValueError

# WRONG: mutating frozen config
cfg = VdemConfig()
cfg.timeout = 600  # AttributeError
```

---

## 10. Test Alignment

- **Green:** Default construction, frozen enforcement, custom variables, output_path construction
- **Beige:** Empty variables rejection, duplicate variable rejection, empty string rejection, zero timeout, empty version
- **Red:** Network failure records ledger, corrupt ZIP raises, malformed CSV raises ValueError

Tests in `tests/test_vdem_harvester.py`.

---

## End of Contract

This document defines the **intended meaning** of `VdemConfig`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
