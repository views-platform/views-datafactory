# Class Intent Contract: UcdpCandidateConfig

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-04-22
**Related ADRs:** ADR-009, ADR-012, ADR-015, ADR-027

---

## 1. Purpose

> Immutable configuration for fetching UCDP/GED Candidate Monthly data from the UCDP API.

Governs version discovery (automatic sequential probing from a start date), API transport, rate limiting, and storage. No explicit version field — versions are discovered at fetch time.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** store a fixed version (versions are discovered dynamically)
- This class does **not** validate API token availability (that is `get_ucdp_token`)
- This class does **not** validate path existence (directories may not exist yet)
- This class does **not** perform any I/O or network access
- This class does **not** know about consolidation, viewpoints, or compilation

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Guarantees all parameters are valid after construction (`__post_init__` validation)
- Guarantees `start_month` is in `[1, 12]`
- Guarantees `start_year >= 1`
- Guarantees `page_size >= 1`
- Guarantees `max_retries >= 1`
- Guarantees `timeout >= 1`
- Guarantees `discovery_rate_limit > 0`
- Guarantees `max_versions >= 1`

---

## 4. Inputs and Assumptions

- `start_year`: int, >= 1, first year for version discovery (default: `CANDIDATE_FIRST_YEAR` = 2018)
- `start_month`: int, in [1, 12], first month for version discovery (default: `CANDIDATE_FIRST_MONTH` = 1)
- `base_url`: str, UCDP API base URL
- `page_size`: int, >= 1, records per API page (default: `1000`)
- `timeout`: int, HTTP request timeout in seconds (default: `30`)
- `max_retries`: int, >= 1, retry attempts on transient failure (default: `3`)
- `discovery_rate_limit`: float, > 0, seconds between discovery probes (default: `0.5`)
- `max_versions`: int, >= 1, maximum versions to discover (default: `120`)
- `data_dir`: Path, output directory for Parquet snapshots
- `ledger_path`: Path, provenance ledger location

Assumptions not met cause immediate `ValueError`.

---

## 5. Outputs and Side Effects

- No side effects. Pure configuration container.
- No derived properties or computed fields.

---

## 6. Failure Modes and Loudness

- `ValueError` on `start_month` outside `[1, 12]`
- `ValueError` on `start_year < 1`
- `ValueError` on `page_size < 1`
- `ValueError` on `max_retries < 1`
- `ValueError` on `timeout < 1`
- `ValueError` on `discovery_rate_limit <= 0`
- `ValueError` on `max_versions < 1`
- `AttributeError` on any attempt to mutate fields (frozen)

All failures are immediate and loud. No silent fallbacks.

---

## 7. Boundaries and Interactions

- Used by `fetch_ucdp_candidate` as the sole configuration input
- Discovery probes construct version strings as `YY.0.MM` from `start_year`/`start_month`
- Storage paths consumed by `save_event_snapshot` and `append_ledger_entry`
- Must not depend on any other `datafactory_*` config class
- Registered in the source registry via `register_source("ucdp_candidate", ...)`

---

## 8. Examples of Correct Usage

```python
cfg = UcdpCandidateConfig()  # From 2018-01, discover up to 120 versions
cfg = UcdpCandidateConfig(start_year=2025, start_month=1)  # Recent only
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: month out of range
UcdpCandidateConfig(start_month=13)  # ValueError

# WRONG: negative rate limit
UcdpCandidateConfig(discovery_rate_limit=-1)  # ValueError
```

---

## 10. Test Alignment

- **Green:** Default construction, custom parameters
- **Beige:** Invalid month, zero year, zero page_size, negative rate limit, zero max_versions
- **Red:** Mutation attempt (frozen enforcement)

Tests in `tests/test_ucdp_candidate.py`.

---

## End of Contract

This document defines the **intended meaning** of `UcdpCandidateConfig`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
