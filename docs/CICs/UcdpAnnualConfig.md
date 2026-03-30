# Class Intent Contract: UcdpAnnualConfig

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-03-22
**Related ADRs:** ADR-009, ADR-012, ADR-015

---

## 1. Purpose

> Immutable configuration for fetching UCDP/GED Annual data from the UCDP API.

Separates harvesting concerns from reporting concerns (SRP). Contains dataset identity (version, year range), API transport parameters (URL, pagination, retry), and storage paths. No ranking, escalation, or analysis parameters.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** store report parameters (ranking_months, top_n_countries)
- This class does **not** validate API token availability (that is `get_ucdp_token`)
- This class does **not** validate path existence (directories may not exist yet)
- This class does **not** perform any I/O or network access
- This class does **not** know about consolidation, viewpoints, or compilation

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Guarantees all parameters are valid after construction (`__post_init__` validation)
- Guarantees `end_year >= start_year`
- Guarantees `page_size >= 1`
- Guarantees `max_retries >= 1`
- Guarantees `page_delay > 0`
- Guarantees `version` is non-empty

---

## 4. Inputs and Assumptions

- `version`: str, non-empty UCDP version identifier (default: `"25.1"`)
- `start_year`: int, first year of data range (default: `1989`)
- `end_year`: int, last year of data range (default: `2024`)
- `base_url`: str, UCDP API base URL
- `page_size`: int, >= 1, records per API page (default: `1000`; production override: `50000` in `harvest_ucdp.py` to avoid API rate-limiting)
- `timeout`: int, HTTP request timeout in seconds (default: `30`)
- `max_retries`: int, >= 1, retry attempts on transient failure (default: `3`)
- `page_delay`: float, > 0, seconds between paginated requests (default: `2.0`)
- `data_dir`: Path, output directory for Parquet snapshots
- `ledger_path`: Path, provenance ledger location

Assumptions not met cause immediate `ValueError`.

---

## 5. Outputs and Side Effects

- No side effects. Pure configuration container.
- No derived properties or computed fields.

---

## 6. Failure Modes and Loudness

- `ValueError` on `end_year < start_year`
- `ValueError` on `page_size < 1`
- `ValueError` on `max_retries < 1`
- `ValueError` on empty `version`
- `AttributeError` on any attempt to mutate fields (frozen)

All failures are immediate and loud. No silent fallbacks.

---

## 7. Boundaries and Interactions

- Used by `fetch_ucdp_annual` as the sole configuration input
- Storage paths consumed by `save_event_snapshot` and `append_ledger_entry`
- Must not depend on any other `datafactory_*` config class
- Registered in the source registry via `register_source("ucdp_annual", ...)`

---

## 8. Examples of Correct Usage

```python
cfg = UcdpAnnualConfig()  # Standard: v25.1, 1989-2024
cfg = UcdpAnnualConfig(version="24.1", end_year=2023)  # Prior version
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: end_year before start_year
UcdpAnnualConfig(start_year=2024, end_year=1989)  # ValueError

# WRONG: empty version
UcdpAnnualConfig(version="")  # ValueError
```

---

## 10. Test Alignment

- **Green:** Default construction, custom parameters
- **Beige:** Inverted year range, zero page_size, zero retries, empty version
- **Red:** Mutation attempt (frozen enforcement)

Tests in `tests/test_ucdp_annual.py`.

---

## End of Contract

This document defines the **intended meaning** of `UcdpAnnualConfig`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
